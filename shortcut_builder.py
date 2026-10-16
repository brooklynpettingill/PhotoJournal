"""Generate an explicitly wired Shortcut and sign it with Apple's macOS CLI.

Run standalone from a PhotoJournal checkout, or call signed_shortcut from the app.
Never publish a generated file: it contains the local receiver's private key.
"""
import argparse
import json
import os
import platform
import plistlib
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlsplit


def token(value):
    return {'Value': value, 'WFSerializationType': 'WFTextTokenAttachment'}


def output(identifier, name):
    return {'Type': 'ActionOutput', 'OutputUUID': identifier, 'OutputName': name}


def text(value):
    if isinstance(value, dict):
        return {'Value': {'string': '\ufffc', 'attachmentsByRange': {'{0, 1}': value}},
                'WFSerializationType': 'WFTextTokenString'}
    return {'Value': {'string': value, 'attachmentsByRange': {}}, 'WFSerializationType': 'WFTextTokenString'}


def dictionary(values):
    return {'Value': {'WFDictionaryFieldValueItems': [
        {'WFItemType': 0, 'WFKey': text(key), 'WFValue': text(value)}
        for key, value in values.items()
    ]}, 'WFSerializationType': 'WFDictionaryFieldValue'}


def build_shortcut(url, key, test=True):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or not parsed.hostname or parsed.path != '/import' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Use the local upload address displayed by PhotoJournal.')
    if not isinstance(key, str) or len(key) < 32 or '\n' in key or '\r' in key:
        raise ValueError('Enable iPhone uploads in PhotoJournal before creating the Shortcut.')
    actions = []

    def action(identifier, **parameters):
        uid = str(uuid.uuid4()).upper()
        parameters['UUID'] = uid
        actions.append({'WFWorkflowActionIdentifier': 'is.workflow.actions.' + identifier,
                        'WFWorkflowActionParameters': parameters})
        return uid

    action('comment', WFCommentActionText=(
        'Private PhotoJournal connection: do not publish or share this Shortcut publicly. '
        'The Mac must be awake on the same trusted home Wi-Fi with PhotoJournal running. '
        + ('This test sends the latest TWO photos. ' if test else
           'This daily version checks the latest 100 photos, not a two-day date filter. Repeat copies are skipped by the Mac. Increase the count after a busy day if needed. ')
        + 'Date and image inputs are explicitly linked to the individual Repeat Item.'))
    photos = action('getlastphoto', WFGetLatestPhotoCount=2 if test else 100,
                    WFGetLatestPhotosActionIncludeScreenshots=True)
    group = str(uuid.uuid4()).upper()
    action('repeat.each', WFControlFlowMode=0, GroupingIdentifier=group,
           WFInput=token(output(photos, 'Latest Photos')))
    item = token({'Type': 'Variable', 'VariableName': 'Repeat Item'})
    captured = action('properties.images', WFContentItemPropertyName='Date Taken', WFInput=item)
    captured_input = token(output(captured, 'Date Taken'))
    formatted = action('format.date', WFDateFormatStyle='Custom', WFDateFormat='yyyy-MM-dd',
                       WFTimeFormatStyle='None', WFInput=captured_input, WFDate=captured_input)
    converted = action('image.convert', WFInput=item, WFImageFormat='JPEG',
                       WFImageCompressionQuality=0.9, WFImagePreserveMetadata=True)
    action('downloadurl', WFURL=url, WFHTTPMethod='POST', Advanced=True, ShowHeaders=True,
           WFHTTPBodyType='File', WFRequestVariable=token(output(converted, 'Converted Image')),
           WFHTTPHeaders=dictionary({'Authorization': 'Bearer ' + key,
                                     'X-Photo-Date': output(formatted, 'Formatted Date'),
                                     'Content-Type': 'image/jpeg'}))
    end = action('repeat.each', WFControlFlowMode=2, GroupingIdentifier=group)
    if test:
        action('showresult', Text=text(output(end, 'Repeat Results')))
    else:
        action('notification', WFNotificationActionTitle='PhotoJournal',
               WFNotificationActionBody='Daily upload run finished. Check PhotoJournal on your Mac to confirm imported photos.',
               WFNotificationActionSound=False)
    workflow = {
        'WFWorkflowActions': actions,
        'WFWorkflowClientVersion': '1200',
        'WFWorkflowClientRelease': '5.0',
        'WFWorkflowMinimumClientVersion': 900,
        'WFWorkflowMinimumClientVersionString': '900',
        'WFWorkflowIcon': {'WFWorkflowIconStartColor': 1239428095, 'WFWorkflowIconGlyphNumber': 59511},
        'WFWorkflowImportQuestions': [],
        'WFWorkflowInputContentItemClasses': [],
        'WFWorkflowTypes': [],
        'WFWorkflowName': 'PhotoJournal Test' if test else 'PhotoJournal Daily',
    }
    return plistlib.dumps(workflow, fmt=plistlib.FMT_BINARY, sort_keys=False)


def signed_shortcut(url, key, test=True):
    unsigned = build_shortcut(url, key, test)
    if platform.system() != 'Darwin' or not Path('/usr/bin/shortcuts').is_file():
        raise RuntimeError('Apple Shortcut signing requires your Mac, with the Shortcuts app available (macOS Monterey or later).')
    with tempfile.TemporaryDirectory(prefix='photojournal-shortcut-') as directory:
        source = Path(directory) / 'unsigned.shortcut'
        target = Path(directory) / 'PhotoJournal.shortcut'
        source.write_bytes(unsigned)
        source.chmod(0o600)
        try:
            subprocess.run(['/usr/bin/shortcuts', 'sign', '--mode', 'anyone',
                            '--input', str(source), '--output', str(target)],
                           capture_output=True, check=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeError('Apple could not sign the Shortcut. Open the Shortcuts app on your Mac, complete any Apple Account setup it requests, then try again.') from error
        if not target.is_file() or target.stat().st_size == 0:
            raise RuntimeError('Apple did not produce a signed Shortcut file.')
        return target.read_bytes()


def main():
    parser = argparse.ArgumentParser(description='Create private PhotoJournal Shortcuts on this Mac.')
    parser.add_argument('--daily', action='store_true', help='Also create the latest-100-photo daily version.')
    args = parser.parse_args()
    root = Path.cwd()
    if not (root / 'app.py').is_file() or not (root / 'phone_import.py').is_file():
        raise SystemExit('Run this command from your PhotoJournal folder in Terminal.')
    sys.path.insert(0, str(root))
    from phone_import import home_address
    data = Path(os.environ.get('PHOTOJOURNAL_DATA', root / 'data')).resolve()
    try:
        config = json.loads((data / 'iphone-receiver.json').read_text())
    except (OSError, ValueError):
        raise SystemExit('Enable iPhone uploads in PhotoJournal first.')
    address = home_address()
    if not config.get('enabled') or not address:
        raise SystemExit('Enable iPhone uploads and connect the Mac to your home Wi-Fi first.')
    url = f'http://{address}:{int(os.environ.get("PHOTOJOURNAL_PHONE_PORT", "3002"))}/import'
    destination = data / 'private-shortcuts'
    destination.mkdir(mode=0o700, exist_ok=True)
    paths = []
    for test in ([True, False] if args.daily else [True]):
        signed = signed_shortcut(url, config.get('token'), test)
        path = destination / ('PhotoJournal Test.shortcut' if test else 'PhotoJournal Daily.shortcut')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(signed)
        paths.append(path)
        print('Created:', path)
    subprocess.run(['/usr/bin/open', '-R', str(paths[0])], check=False)
    print('In Finder: right-click the test file → Share → AirDrop → your iPhone, then open it in Shortcuts.')
    print('Keep these files private: they include your upload key. Test on the iPhone before scheduling.')


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError) as error:
        raise SystemExit(str(error))
