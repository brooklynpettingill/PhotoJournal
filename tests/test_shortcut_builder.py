import plistlib
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch
from shortcut_builder import build_shortcut, signed_shortcut
from app import app, phone_receiver

KEY = 'test-only-connection-key-not-a-real-secret'
URL = 'http://192.168.1.10:3002/import'


class ShortcutBuilderTest(unittest.TestCase):
    def test_wire_each_photo_and_formatted_date_by_source(self):
        workflow = plistlib.loads(build_shortcut(URL, KEY))
        actions = workflow['WFWorkflowActions']
        by_kind = {a['WFWorkflowActionIdentifier'].split('.')[-1]: a['WFWorkflowActionParameters'] for a in actions}
        first = actions[1]['WFWorkflowActionParameters']
        repeat = actions[2]['WFWorkflowActionParameters']
        details = actions[3]['WFWorkflowActionParameters']
        formatted = actions[4]['WFWorkflowActionParameters']
        converted = actions[5]['WFWorkflowActionParameters']
        upload = actions[6]['WFWorkflowActionParameters']
        end = actions[7]['WFWorkflowActionParameters']
        self.assertEqual(first['WFGetLatestPhotoCount'], 2)
        self.assertEqual(repeat['WFInput']['Value']['OutputUUID'], first['UUID'])
        for action in (details, converted):
            self.assertEqual(action['WFInput']['Value'], {'Type':'Variable','VariableName':'Repeat Item'})
        self.assertEqual(details['WFContentItemPropertyName'], 'Date Taken')
        self.assertEqual(formatted['WFInput']['Value']['OutputUUID'], details['UUID'])
        self.assertEqual(formatted['WFDateFormat'], 'yyyy-MM-dd')
        self.assertEqual(upload['WFRequestVariable']['Value']['OutputUUID'], converted['UUID'])
        self.assertEqual(upload['WFHTTPMethod'], 'POST')
        self.assertEqual(upload['WFHTTPBodyType'], 'File')
        headers = {row['WFKey']['Value']['string']:row['WFValue']['Value'] for row in upload['WFHTTPHeaders']['Value']['WFDictionaryFieldValueItems']}
        self.assertEqual(headers['Authorization']['string'], 'Bearer '+KEY)
        date_reference = headers['X-Photo-Date']['attachmentsByRange']['{0, 1}']
        self.assertEqual(date_reference['OutputUUID'], formatted['UUID'])
        self.assertEqual(date_reference['Type'], 'ActionOutput')
        self.assertNotIn('Aggrandizements', date_reference)
        self.assertEqual(repeat['GroupingIdentifier'], end['GroupingIdentifier'])
        self.assertEqual(end['WFControlFlowMode'], 2)

    def test_daily_variant_has_bounded_selection_and_no_dialog(self):
        actions = plistlib.loads(build_shortcut(URL, KEY, False))['WFWorkflowActions']
        self.assertEqual(actions[1]['WFWorkflowActionParameters']['WFGetLatestPhotoCount'], 100)
        self.assertTrue(actions[-1]['WFWorkflowActionIdentifier'].endswith('.notification'))
        self.assertFalse(any(a['WFWorkflowActionIdentifier'].endswith('.showresult') for a in actions))

    def test_rejects_missing_pairing_and_unsafe_url(self):
        for url,key in [('https://example.com/',KEY),(URL,''),('http://user:password@192.168.1.10/import',KEY)]:
            with self.assertRaises(ValueError):
                build_shortcut(url,key)

    def test_signing_requires_mac_and_does_not_claim_unsigned_file_ready(self):
        with patch('shortcut_builder.platform.system', return_value='Linux'):
            with self.assertRaisesRegex(RuntimeError, 'requires your Mac'):
                signed_shortcut(URL,KEY)

    def test_uses_apple_signer_and_cleans_temporary_files(self):
        locations = []
        def sign(command, **kwargs):
            source = Path(command[command.index('--input')+1])
            destination = Path(command[command.index('--output')+1])
            locations.extend([source,destination])
            self.assertEqual(command[:4], ['/usr/bin/shortcuts','sign','--mode','anyone'])
            self.assertEqual(source.stat().st_mode & 0o777, 0o600)
            self.assertIn('WFWorkflowActions', plistlib.loads(source.read_bytes()))
            destination.write_bytes(b'fake-signed-output-for-test-only')
        with patch('shortcut_builder.platform.system',return_value='Darwin'), patch('shortcut_builder.Path.is_file',return_value=True), patch('shortcut_builder.subprocess.run',side_effect=sign):
            self.assertEqual(signed_shortcut(URL,KEY),b'fake-signed-output-for-test-only')
        self.assertTrue(all(not p.exists() for p in locations))

    def test_download_endpoint_returns_file_or_safe_error(self):
        client = app.test_client()
        with patch.object(phone_receiver,'available',True), patch.object(phone_receiver,'enabled',True), patch.object(phone_receiver,'status',return_value={'url':URL,'token':KEY}):
            with patch('shortcut_builder.signed_shortcut',return_value=b'test-file') as signer:
                response = client.post('/api/sources/iphone/shortcut',json={'test':True})
                self.assertEqual(response.status_code,200)
                self.assertIn('attachment',response.headers['Content-Disposition'])
                signer.assert_called_once_with(URL,KEY,test=True)
                response.close()
            with patch('shortcut_builder.signed_shortcut',side_effect=RuntimeError('Open Shortcuts on your Mac.')):
                self.assertEqual(client.post('/api/sources/iphone/shortcut',json={}).status_code,400)

if __name__ == '__main__': unittest.main()
