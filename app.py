import os
import hashlib
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from PIL import Image, ImageOps, UnidentifiedImageError

app = Flask(__name__, static_folder='static')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
from security import configure_security
configure_security(app)
DATA = Path(os.environ.get('PHOTOJOURNAL_DATA', 'data')).resolve()
DATA.mkdir(parents=True, exist_ok=True)
(DATA / 'photos').mkdir(exist_ok=True)

@contextmanager
def db():
    conn = sqlite3.connect(DATA / 'journal.sqlite3', timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            conn.execute('CREATE TABLE IF NOT EXISTS pages (day TEXT PRIMARY KEY, caption TEXT NOT NULL DEFAULT "", approved INTEGER NOT NULL DEFAULT 0)')
            conn.execute('CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, day TEXT NOT NULL, selected INTEGER NOT NULL DEFAULT 1)')
            conn.execute('CREATE TABLE IF NOT EXISTS imports (source_id TEXT PRIMARY KEY, photo_id TEXT NOT NULL)')
            yield conn
    finally:
        conn.close()


def already_imported(source_id):
    with db() as conn:
        return conn.execute('SELECT 1 FROM imports WHERE source_id=?', (source_id,)).fetchone() is not None


def ingest_photo(stream, fallback, source_id=None, capture_day=None):
    """Save one photo; source IDs make recurring Apple imports idempotent."""
    date.fromisoformat(fallback)
    if source_id and already_imported(source_id):
        return None
    identifier = uuid.uuid4().hex
    target = DATA / 'photos' / (identifier + '.jpg')
    try:
        with Image.open(stream) as original:
            exif_date = original.getexif().get(36867) or original.getexif().get(306)
            try:
                day = datetime.strptime(str(exif_date)[:10], '%Y:%m:%d').date().isoformat()
            except ValueError:
                day = fallback
            if capture_day:
                day = date.fromisoformat(capture_day).isoformat()
            image = ImageOps.exif_transpose(original).convert('RGB')
            image.thumbnail((3000, 3000))
            if source_id == 'iphone':
                fingerprint = hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()
                source_id = 'iphone:' + day + ':' + fingerprint
                if already_imported(source_id):
                    return None
            image.save(target, 'JPEG', quality=92)
        with db() as conn:
            if source_id:
                claimed = conn.execute('INSERT OR IGNORE INTO imports VALUES (?, ?)', (source_id, identifier)).rowcount
                if not claimed:
                    target.unlink(missing_ok=True)
                    return None
            conn.execute('INSERT OR IGNORE INTO pages(day) VALUES (?)', (day,))
            count = conn.execute('SELECT count(*) FROM photos WHERE day=? AND selected=1', (day,)).fetchone()[0]
            conn.execute('INSERT INTO photos VALUES (?, ?, ?)', (identifier, day, int(count < 6)))
            conn.execute('UPDATE pages SET approved=0 WHERE day=?', (day,))
        return day
    except Exception:
        target.unlink(missing_ok=True)
        raise


@app.get('/healthz')
def health():
    return jsonify(status='ok')

@app.get('/')
def index():
    return app.send_static_file('index.html')

@app.get('/api/pages')
def pages():
    with db() as conn:
        result = []
        for row in conn.execute('SELECT * FROM pages ORDER BY day'):
            page = dict(row)
            page['photos'] = [dict(p) for p in conn.execute('SELECT id, selected FROM photos WHERE day=? ORDER BY rowid', (row['day'],))]
            result.append(page)
    return jsonify(result)

@app.post('/api/upload')
def upload():
    fallback = request.form.get('day', '')
    try:
        date.fromisoformat(fallback)
    except ValueError:
        return jsonify(error='Choose a valid fallback date.'), 400
    added, errors = [], []
    for f in request.files.getlist('photos'):
        try:
            added.append(ingest_photo(f.stream, fallback))
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            errors.append(f.filename)
    return jsonify(added=added, rejected=errors), (200 if added else 400)

@app.patch('/api/pages/<day>')
def update(day):
    body = request.get_json(silent=True) or {}
    with db() as conn:
        if not conn.execute('SELECT 1 FROM pages WHERE day=?', (day,)).fetchone():
            return jsonify(error='Page not found.'), 404
        if 'selected' in body:
            chosen = body['selected']
            if not isinstance(chosen, list) or not 1 <= len(chosen) <= 6 or any(not isinstance(x, str) for x in chosen):
                return jsonify(error='Choose one to six photos.'), 400
            available = {r['id'] for r in conn.execute('SELECT id FROM photos WHERE day=?', (day,))}
            if not set(chosen) <= available:
                return jsonify(error='Photo does not belong to this day.'), 400
            conn.execute('UPDATE photos SET selected=0 WHERE day=?', (day,))
            conn.executemany('UPDATE photos SET selected=1 WHERE id=? AND day=?', [(x, day) for x in chosen])
        if 'caption' in body:
            if not isinstance(body['caption'], str) or len(body['caption']) > 4000:
                return jsonify(error='Caption must be text under 4,000 characters.'), 400
            conn.execute('UPDATE pages SET caption=? WHERE day=?', (body['caption'], day))
        conn.execute('UPDATE pages SET approved=? WHERE day=?', (int(bool(body.get('approved', False))), day))
    return jsonify(ok=True)

@app.get('/photos/<identifier>.jpg')
def photo(identifier):
    if len(identifier) != 32 or any(c not in '0123456789abcdef' for c in identifier):
        return '', 404
    return send_from_directory(DATA / 'photos', identifier + '.jpg')

@app.errorhandler(413)
def too_large(_):
    return jsonify(error='Upload up to 100 MB at a time.'), 413

from apple_sync import AppleSync
apple_sync = AppleSync(DATA, ingest_photo, already_imported)

@app.get('/api/sources/apple')
def apple_status():
    return jsonify(apple_sync.status())

@app.post('/api/sources/apple')
def configure_apple():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('enabled'), bool):
        return jsonify(error='Specify whether to enable Apple Photos sync.'), 400
    if not apple_sync.available:
        return jsonify(error='Open the Mac version of PhotoJournal to connect Apple Photos.'), 501
    try:
        apple_sync.configure(body['enabled'])
    except OSError:
        return jsonify(error='Could not save the photo connection. Check that your journal folder is writable.'), 500
    return jsonify(apple_sync.status())

from phone_import import PhoneReceiver
phone_receiver = PhoneReceiver(DATA, ingest_photo)

@app.get('/api/sources/iphone')
def iphone_status():
    return jsonify(phone_receiver.status())

@app.post('/api/sources/iphone')
def configure_iphone():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or not isinstance(body.get('enabled'), bool):
        return jsonify(error='Specify whether to enable iPhone uploads.'), 400
    if not phone_receiver.available:
        return jsonify(error='Use the local Mac version of PhotoJournal for iPhone uploads.'), 501
    try:
        phone_receiver.configure(body['enabled'])
    except OSError:
        return jsonify(error='Could not start or save the receiver. Stop any other copy of PhotoJournal, check the folder is writable, and retry.'), 500
    return jsonify(phone_receiver.status())

if __name__ == '__main__':
    app.config['TRUSTED_HOSTS'] = ['127.0.0.1', 'localhost', '[::1]']
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 3000)))
