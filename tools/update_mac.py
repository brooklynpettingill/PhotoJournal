"""Update an extracted ZIP checkout without touching photographs or database files."""
import shutil
import subprocess
import tempfile
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

FILES = [
    'app.py', 'apple_sync.py', 'phone_import.py', 'security.py', 'wsgi.py', 'requirements.txt',
    'static/index.html', 'static/app.js', 'static/style.css',
    'tests/test_app.py', 'tests/test_security.py', 'tests/test_apple_sync.py', 'tests/test_mac_updater.py', 'tests/test_phone_import.py',
    'tools/password_hash.py', 'tools/update_mac.py',
    'README.md', 'HOSTING.md', 'APPLE_PHOTOS.md', 'IPHONE_SHORTCUT.md', 'Dockerfile', '.dockerignore', '.gitignore',
]


def update():
    root = Path.cwd()
    if not (root / 'app.py').is_file() or not (root / 'requirements.txt').is_file():
        raise SystemExit('First open Terminal in your PhotoJournal folder.')
    with tempfile.TemporaryDirectory(prefix='photojournal-update-') as directory:
        archive = Path(directory) / 'update.zip'
        subprocess.run(['curl', '--fail', '--location', '--proto', '=https', '--tlsv1.2',
                        '--max-time', '120', '--output', str(archive),
                        'https://codeload.github.com/brooklynpettingill/PhotoJournal/zip/refs/heads/main'], check=True)
        with zipfile.ZipFile(archive) as z:
            # Fixed allowlist; never extract archive paths, data, credentials or symlinks.
            updates = {name: z.read('PhotoJournal-main/' + name) for name in FILES}
        backup = root / '.updates-backup' / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6])
        backup.mkdir(parents=True)
        for name in FILES:
            source = root / name
            if source.exists():
                target = backup / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        applied = []
        try:
            for name, data in updates.items():
                destination = root / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                applied.append(name)
                destination.write_bytes(data)
        except Exception:
            for name in applied:
                original = backup / name
                if original.exists():
                    shutil.copy2(original, root / name)
                else:
                    (root / name).unlink(missing_ok=True)
            raise
    print('Updated PhotoJournal. Your data folder was not changed.')
    print('Previous application files were saved in:', backup)


if __name__ == '__main__':
    update()
