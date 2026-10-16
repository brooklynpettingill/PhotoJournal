"""Opt-in home-network upload receiver; never serves journal data."""
import hmac
import ipaddress
import json
import os
import platform
import secrets
import subprocess
import threading
from datetime import date, datetime, timezone

from flask import Flask, jsonify, request
from PIL import Image, UnidentifiedImageError
from werkzeug.serving import WSGIRequestHandler, make_server


def home_address():
    if platform.system() != 'Darwin':
        return None
    for interface in ('en0', 'en1', 'en2'):
        try:
            value = subprocess.run(['/usr/sbin/ipconfig', 'getifaddr', interface],
                                   capture_output=True, text=True, timeout=5, check=True).stdout.strip()
            if ipaddress.IPv4Address(value).is_private:
                return value
        except (OSError, ValueError, subprocess.SubprocessError):
            continue
    return None


class QuietHandler(WSGIRequestHandler):
    def log(self, *args, **kwargs):
        pass


class PhoneReceiver:
    def __init__(self, data, ingest):
        self.data, self.ingest = data, ingest
        self.available = platform.system() == 'Darwin'
        self.lock = threading.RLock()
        self.server = self.thread = None
        self.token = None
        self.enabled = False
        self.error = None
        self.last_received = None
        self.imported = 0
        self.port = int(os.environ.get('PHOTOJOURNAL_PHONE_PORT', '3002'))
        self.receiver = self._application()
        try:
            config = json.loads((data / 'iphone-receiver.json').read_text())
            self.enabled = config.get('enabled') is True
            token = config.get('token')
            self.token = token if isinstance(token, str) and len(token) >= 32 else None
        except (OSError, ValueError):
            pass
        if self.available and self.enabled and self.token:
            try:
                self._start()
            except (OSError, SystemExit):
                self.enabled = False
                self.error = 'Could not start the iPhone receiver. Port 3002 may already be in use.'

    def _application(self):
        receiver = Flask('phone_receiver', static_folder=None)
        receiver.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

        @receiver.before_request
        def authenticate():
            if request.path != '/import' or request.method != 'POST':
                return '', 404
            try:
                peer = ipaddress.ip_address(request.remote_addr)
                local = peer.is_private or peer.is_loopback
            except ValueError:
                local = False
            if not local:
                return jsonify(error='Use your trusted home network.'), 403
            if request.headers.get('Origin') or request.headers.get('Sec-Fetch-Site') == 'cross-site':
                return jsonify(error='Browser uploads are not supported on this receiver.'), 403
            supplied = request.headers.get('Authorization', '')
            expected = 'Bearer ' + (self.token or '')
            if not self.enabled or not self.token or not hmac.compare_digest(supplied.encode(), expected.encode()):
                return jsonify(error='Invalid private upload key.'), 401

        @receiver.post('/import')
        def receive():
            day = request.headers.get('X-Photo-Date', '')
            try:
                date.fromisoformat(day)
            except ValueError:
                return jsonify(error='Send the capture date as X-Photo-Date: yyyy-MM-dd.'), 400
            body = request.get_data()
            if not body:
                return jsonify(error='Send one JPEG photo as the request body.'), 400
            import io
            source_id = 'iphone'  # Ingestion derives a stable key from oriented, resized pixels.
            try:
                added = self.ingest(io.BytesIO(body), day, source_id=source_id, capture_day=day)
            except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
                return jsonify(error='Could not read this photo. Convert it to JPEG in the Shortcut.'), 400
            with self.lock:
                self.last_received = datetime.now(timezone.utc).isoformat()
                self.imported += int(added is not None)
            return jsonify(day=day, imported=added is not None, duplicate=added is None)

        @receiver.errorhandler(413)
        def large(_):
            return jsonify(error='Send one photo under 25 MB at a time.'), 413

        @receiver.after_request
        def headers(response):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Content-Type-Options'] = 'nosniff'
            return response
        return receiver

    def _start(self):
        if self.server is None:
            self.server = make_server('0.0.0.0', self.port, self.receiver, threaded=True, request_handler=QuietHandler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True, name='iphone-upload')
            self.thread.start()

    def configure(self, enabled):
        if not self.available:
            raise RuntimeError('The iPhone receiver is available only in the local Mac app.')
        with self.lock:
            if enabled and not self.token:
                self.token = secrets.token_urlsafe(32)
            if enabled:
                try:
                    self._start()
                except (OSError, SystemExit):
                    raise OSError('Port 3002 is unavailable. Stop any other copy of PhotoJournal and retry.')
            else:
                if self.server:
                    self.server.shutdown()
                    self.server.server_close()
                    self.server = self.thread = None
            config = self.data / 'iphone-receiver.json'
            temporary = config.with_suffix('.tmp')
            try:
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, 'w') as stream:
                    json.dump({'enabled': enabled, 'token': self.token}, stream)
                temporary.replace(config)
            except OSError:
                if self.server:
                    self.server.shutdown()
                    self.server.server_close()
                    self.server = self.thread = None
                self.enabled = False
                raise
            self.enabled = enabled
            self.error = None

    def status(self):
        address = home_address() if self.available else None
        with self.lock:
            return dict(available=self.available, enabled=self.enabled,
                        running=self.server is not None, error=self.error,
                        url=f'http://{address}:{self.port}/import' if address and self.enabled else None,
                        token=self.token if self.enabled else None,
                        last_received=self.last_received, imported=self.imported)
