"""Single-owner authentication for HTTPS deployments."""
import hmac
import os
from urllib.parse import urlsplit
from flask import Response, jsonify, request
from werkzeug.security import check_password_hash


def configure_security(app):
    app.config.update(
        JOURNAL_USERNAME=os.environ.get('PHOTOJOURNAL_USERNAME', 'owner'),
        JOURNAL_PASSWORD_HASH=os.environ.get('PHOTOJOURNAL_PASSWORD_HASH', ''),
    )

    @app.before_request
    def protect():
        if request.path == '/healthz':
            return None
        password_hash = app.config['JOURNAL_PASSWORD_HASH']
        if password_hash:
            auth = request.authorization
            valid = bool(auth and auth.type.lower() == 'basic'
                         and hmac.compare_digest(auth.username or '', app.config['JOURNAL_USERNAME'])
                         and check_password_hash(password_hash, auth.password or ''))
            if not valid:
                return Response('Sign in to your private photo journal.', 401,
                                {'WWW-Authenticate': 'Basic realm="PhotoJournal", charset="UTF-8"',
                                 'Cache-Control': 'no-store'})
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('Origin')
            # Reject cross-site requests, including requests with ambient Basic credentials.
            if (request.headers.get('Sec-Fetch-Site') == 'cross-site'
                    or (origin and urlsplit(origin).netloc != request.host)):
                return jsonify(error='Cross-site requests are not allowed.'), 403

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
