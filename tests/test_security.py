import base64
import unittest
from werkzeug.security import generate_password_hash
from app import app

class SecurityTest(unittest.TestCase):
    def setUp(self):
        self.original = app.config['JOURNAL_PASSWORD_HASH']
        app.config['JOURNAL_PASSWORD_HASH'] = generate_password_hash('test-only-password')
        self.client = app.test_client()
        self.auth = {'Authorization': 'Basic '+base64.b64encode(b'owner:test-only-password').decode()}

    def tearDown(self):
        app.config['JOURNAL_PASSWORD_HASH'] = self.original

    def test_private_resources_require_login(self):
        for path in ['/', '/api/pages', '/static/app.js', '/photos/'+'a'*32+'.jpg']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get('/healthz').status_code, 200)
        self.assertEqual(self.client.get('/', headers=self.auth).status_code, 200)
        wrong = {'Authorization':'Basic '+base64.b64encode(b'owner:wrong').decode()}
        self.assertEqual(self.client.get('/api/pages',headers=wrong).status_code, 401)

    def test_cross_site_write_blocked(self):
        headers = dict(self.auth, Origin='https://another-site.example')
        self.assertEqual(self.client.post('/api/upload',headers=headers).status_code, 403)
        headers = dict(self.auth, **{'Sec-Fetch-Site':'cross-site'})
        self.assertEqual(self.client.patch('/api/pages/2023-01-02',headers=headers,json={}).status_code, 403)

if __name__ == '__main__': unittest.main()
