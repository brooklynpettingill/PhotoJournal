import io
import tempfile
import unittest
import urllib.request
import urllib.error
import json
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from phone_import import PhoneReceiver
from app import ingest_photo, db


def jpeg():
    body = io.BytesIO()
    Image.new('RGB', (41, 31), 'orange').save(body, 'JPEG')
    return body.getvalue()


class PhoneImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.receiver = PhoneReceiver(Path(self.temp.name), ingest_photo)
        self.receiver.enabled = True
        self.receiver.token = 'test-only-token-not-a-real-secret'
        self.client = self.receiver.receiver.test_client()
        self.headers = {'Authorization':'Bearer '+self.receiver.token, 'X-Photo-Date':'2025-07-08', 'Content-Type':'image/jpeg'}

    def tearDown(self):
        self.temp.cleanup()

    def test_upload_duplicate_and_private_routes(self):
        body = jpeg()
        first = self.client.post('/import', headers=self.headers, data=body)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json['imported'])
        with db() as conn:
            conn.execute('UPDATE pages SET approved=1 WHERE day=?', ('2025-07-08',))
        second = self.client.post('/import', headers=self.headers, data=body)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json['duplicate'])
        with db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM photos WHERE day=?', ('2025-07-08',)).fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT approved FROM pages WHERE day=?', ('2025-07-08',)).fetchone()[0], 1)
        for path in ['/', '/api/pages', '/photos/example.jpg', '/import']:
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_rejects_missing_wrong_key_and_external_requests(self):
        self.assertEqual(self.client.post('/import', data=jpeg()).status_code, 401)
        wrong = dict(self.headers, Authorization='Bearer wrong')
        self.assertEqual(self.client.post('/import',headers=wrong,data=jpeg()).status_code, 401)
        foreign = dict(self.headers, Origin='https://untrusted.example')
        self.assertEqual(self.client.post('/import',headers=foreign,data=jpeg()).status_code, 403)
        self.assertEqual(self.client.post('/import',headers=self.headers,data=jpeg(),environ_overrides={'REMOTE_ADDR':'8.8.8.8'}).status_code, 403)
        self.receiver.enabled = False
        self.assertEqual(self.client.post('/import',headers=self.headers,data=jpeg()).status_code, 401)

    def test_requires_valid_date_and_image(self):
        bad_day = dict(self.headers, **{'X-Photo-Date':'yesterday'})
        self.assertEqual(self.client.post('/import',headers=bad_day,data=jpeg()).status_code, 400)
        self.assertEqual(self.client.post('/import',headers=self.headers,data=b'not an image').status_code, 400)
        self.receiver.receiver.config['MAX_CONTENT_LENGTH'] = 10
        self.assertEqual(self.client.post('/import',headers=self.headers,data=jpeg()).status_code, 413)

    def test_live_receiver_restart_and_stop(self):
        self.receiver.enabled = False
        self.receiver.available = True
        self.receiver.port = 0
        headers = dict(self.headers, **{'X-Photo-Date':'2025-09-02'})
        try:
            self.receiver.configure(True)
            url = 'http://127.0.0.1:' + str(self.receiver.server.server_port) + '/import'
            try:
                urllib.request.urlopen(urllib.request.Request(url, data=jpeg()), timeout=3)
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 401)
            else:
                self.fail('Unauthenticated upload accepted')
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, data=jpeg()), timeout=3) as r:
                self.assertTrue(json.load(r)['imported'])
            self.receiver.configure(False)
            with self.assertRaises(OSError):
                urllib.request.urlopen(urllib.request.Request(url, data=jpeg()), timeout=1)
            self.receiver.configure(True)
            url = 'http://127.0.0.1:' + str(self.receiver.server.server_port) + '/import'
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers, data=jpeg()), timeout=3) as r:
                self.assertTrue(json.load(r)['duplicate'])
        finally:
            self.receiver.configure(False)

    def test_connection_config_uses_private_file_permissions(self):
        self.receiver.enabled = False
        self.receiver.available = True
        with patch.object(self.receiver, '_start'):
            self.receiver.configure(True)
        config = Path(self.temp.name) / 'iphone-receiver.json'
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.receiver.configure(False)
        self.assertIsNone(self.receiver.status()['token'])

if __name__ == '__main__': unittest.main()
