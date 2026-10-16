"""Production entrypoint: refuse to serve personal photos without a login."""
import os
from pathlib import Path

if not os.environ.get('PHOTOJOURNAL_PASSWORD_HASH', '').startswith(('scrypt:', 'pbkdf2:')):
    raise RuntimeError('Set PHOTOJOURNAL_PASSWORD_HASH to a Werkzeug password hash before hosting.')
if not os.environ.get('PHOTOJOURNAL_DATA') or not Path(os.environ['PHOTOJOURNAL_DATA']).is_absolute():
    raise RuntimeError('Set PHOTOJOURNAL_DATA to an absolute path on persistent storage.')
from app import app
