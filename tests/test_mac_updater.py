import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from tools import update_mac


class MacUpdaterTest(unittest.TestCase):
    def test_updates_only_code_and_preserves_data_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'app.py').write_text('previous app')
            (root / 'requirements.txt').write_text('previous requirements')
            (root / 'data').mkdir()
            (root / 'data' / 'journal.sqlite3').write_bytes(b'journal to preserve')
            def download(command, **kwargs):
                archive = command[command.index('--output') + 1]
                with zipfile.ZipFile(archive, 'w') as z:
                    for name in update_mac.FILES:
                        z.writestr('PhotoJournal-main/' + name, 'new code')
                    z.writestr('PhotoJournal-main/data/journal.sqlite3', 'unwanted replacement')
                    z.writestr('PhotoJournal-main/../escape', 'unwanted file')
            with patch('tools.update_mac.Path.cwd', return_value=root), patch('tools.update_mac.subprocess.run', side_effect=download):
                update_mac.update()
            self.assertEqual((root / 'app.py').read_text(), 'new code')
            self.assertEqual((root / 'data' / 'journal.sqlite3').read_bytes(), b'journal to preserve')
            self.assertFalse((root / 'escape').exists())
            backups = list((root / '.updates-backup').glob('*/app.py'))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), 'previous app')

if __name__ == '__main__': unittest.main()
