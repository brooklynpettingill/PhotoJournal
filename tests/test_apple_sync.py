import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app import app, db, ingest_photo, already_imported
from apple_sync import AppleSync, recent_photos


def picture():
    stream = io.BytesIO()
    exif = Image.Exif()
    exif[36867] = '2020:01:01 12:00:00'
    Image.new('RGB', (30, 40), 'green').save(stream, 'JPEG', exif=exif)
    stream.seek(0)
    return stream


class AppleSyncTest(unittest.TestCase):
    def test_source_day_and_duplicate_preserve_approval(self):
        source = 'apple:test-same-asset'
        day = '2024-05-06'
        self.assertEqual(ingest_photo(picture(), day, source, capture_day=day), day)
        with db() as conn:
            conn.execute('UPDATE pages SET approved=1 WHERE day=?', (day,))
        self.assertIsNone(ingest_photo(picture(), day, source, capture_day=day))
        with db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM imports WHERE source_id=?', (source,)).fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT count(*) FROM photos WHERE day=?', (day,)).fetchone()[0], 1)
            self.assertEqual(conn.execute('SELECT approved FROM pages WHERE day=?', (day,)).fetchone()[0], 1)
        self.assertTrue(already_imported(source))

    def test_retry_after_export_failure_and_skip_completed(self):
        with tempfile.TemporaryDirectory() as d:
            sync = AppleSync(Path(d), lambda *a, **k: '2024-05-06', lambda x: x == 'apple:old')
            sync.enabled = True
            photo = Path(d) / 'test.jpg'
            photo.write_bytes(picture().getvalue())
            with patch('apple_sync.recent_photos', return_value=[('old','2024-05-06'),('new','2024-05-06')]), patch('apple_sync.export_photo', side_effect=OSError()):
                sync.sync_once()
            self.assertEqual(sync.status()['failed'], 1)
            with patch('apple_sync.recent_photos', return_value=[('old','2024-05-06'),('new','2024-05-06')]), patch('apple_sync.export_photo', return_value=photo) as export:
                sync.sync_once()
                export.assert_called_once()
            self.assertEqual(sync.status()['imported'], 1)
            self.assertFalse(sync.status()['running'])

    def test_query_parsing(self):
        with patch('apple_sync.run_script', return_value='asset-id\t2024-05-06\n'):
            self.assertEqual(recent_photos(), [('asset-id','2024-05-06')])

    def test_permission_error_reported(self):
        with tempfile.TemporaryDirectory() as d:
            sync = AppleSync(Path(d), lambda *a, **k: None, lambda x: False)
            with patch('apple_sync.recent_photos', side_effect=OSError()):
                sync.sync_once()
            self.assertIn('Automation', sync.status()['error'])
            self.assertFalse(sync.status()['running'])

    def test_sync_endpoint_validates_input_and_platform(self):
        client = app.test_client()
        self.assertEqual(client.get('/api/sources/apple').status_code, 200)
        self.assertEqual(client.post('/api/sources/apple',json={'enabled':'yes'}).status_code, 400)
        with patch('app.apple_sync.available', False):
            self.assertEqual(client.post('/api/sources/apple',json={'enabled':True}).status_code, 501)

if __name__ == '__main__': unittest.main()
