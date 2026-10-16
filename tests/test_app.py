import io
import os
import tempfile
import unittest
os.environ['PHOTOJOURNAL_DATA'] = tempfile.mkdtemp(prefix='photojournal-test-')
from app import app
from PIL import Image

class JournalTest(unittest.TestCase):
    def test_workflow(self):
        client = app.test_client()
        self.assertEqual(client.get('/').status_code, 200)
        image = Image.new('RGB', (40, 60), 'green')
        exif = Image.Exif(); exif[36867] = '2023:01:02 12:00:00'
        stream = io.BytesIO(); image.save(stream, 'JPEG', exif=exif); stream.seek(0)
        response = client.post('/api/upload', data={'day':'2026-01-01', 'photos':(stream,'photo.jpg')})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['added'], ['2023-01-02'])
        page = client.get('/api/pages').json[0]
        identifier = page['photos'][0]['id']
        self.assertEqual(client.get('/photos/'+identifier+'.jpg').status_code, 200)
        self.assertEqual(client.patch('/api/pages/2023-01-02',json={'selected':[]}).status_code, 400)
        self.assertEqual(client.patch('/api/pages/2023-01-02',json={'selected':['foreign']}).status_code, 400)
        self.assertEqual(client.patch('/api/pages/2023-01-02',json={'caption':'A day at the cabin.', 'selected':[identifier], 'approved':True}).status_code, 200)
        saved = client.get('/api/pages').json[0]
        self.assertEqual(saved['caption'], 'A day at the cabin.')
        self.assertEqual(saved['approved'], 1)
        self.assertEqual(client.post('/api/upload',data={'day':'bad'}).status_code, 400)
        self.assertEqual(client.post('/api/upload',data={'day':'2026-01-01','photos':(io.BytesIO(b'bad'),'bad.jpg')}).status_code, 400)

if __name__ == '__main__': unittest.main()
