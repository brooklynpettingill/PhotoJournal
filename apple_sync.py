"""Optional, local-only Apple Photos bridge. Never modifies the Photos library."""
import json
import platform
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path

QUERY_SCRIPT = '''
on pad2(n)
    return text -2 thru -1 of ("0" & (n as text))
end pad2
set cutoff to (current date) - (7 * days)
set time of cutoff to 0
set rows to {}
tell application "Photos"
    set recentItems to every media item whose date is greater than or equal to cutoff
    repeat with itemRef in recentItems
        set filenameText to filename of itemRef
        ignoring case
            set supported to filenameText ends with ".jpg" or filenameText ends with ".jpeg" or filenameText ends with ".heic" or filenameText ends with ".heif" or filenameText ends with ".png" or filenameText ends with ".tiff" or filenameText ends with ".tif" or filenameText ends with ".webp"
        end ignoring
        if supported then
            set captured to date of itemRef
            set dayText to ((year of captured) as text) & "-" & my pad2((month of captured) as integer) & "-" & my pad2(day of captured)
            set end of rows to (id of itemRef) & tab & dayText
        end if
    end repeat
end tell
set AppleScript's text item delimiters to linefeed
return rows as text
'''
EXPORT_SCRIPT = '''
on run argv
    set photoID to item 1 of argv
    set destination to POSIX file (item 2 of argv) as alias
    tell application "Photos"
        set matchingItems to every media item whose id is photoID
        if (count matchingItems) is 0 then error "Photo no longer exists"
        export matchingItems to destination with using originals
    end tell
end run
'''


def run_script(script, *args, timeout=180):
    return subprocess.run(['/usr/bin/osascript', '-e', script, '--', *args],
                          capture_output=True, text=True, check=True, timeout=timeout).stdout


def recent_photos():
    rows = []
    for line in run_script(QUERY_SCRIPT).splitlines():
        if not line.strip():
            continue
        identifier, day = line.split('\t', 1)
        datetime.strptime(day, '%Y-%m-%d')
        rows.append((identifier, day))
    return rows


def export_photo(identifier, destination):
    run_script(EXPORT_SCRIPT, identifier, str(destination))
    images = sorted(p for p in destination.rglob('*') if p.is_file()
                    and p.suffix.lower() in {'.jpg', '.jpeg', '.heic', '.heif', '.png', '.tiff', '.tif', '.webp'})
    if not images:
        raise OSError('Original photo not available locally.')
    source = images[0]
    if source.suffix.lower() in {'.heic', '.heif'}:
        converted = destination / 'converted.jpg'
        subprocess.run(['/usr/bin/sips', '-s', 'format', 'jpeg', str(source), '--out', str(converted)],
                       check=True, capture_output=True, timeout=120)
        return converted
    return source


class AppleSync:
    def __init__(self, data, ingest, already_imported):
        self.data = data
        self.ingest = ingest
        self.already_imported = already_imported
        self.available = platform.system() == 'Darwin'
        self.wake = threading.Event()
        self.lock = threading.Lock()
        self.thread = None
        try:
            self.enabled = json.loads((data / 'apple-sync.json').read_text()).get('enabled') is True
        except (OSError, ValueError):
            self.enabled = False
        self.state = {'running': False, 'last_checked': None, 'imported': 0, 'failed': 0, 'error': None}
        if self.enabled and self.available:
            self.start()

    def status(self):
        with self.lock:
            return dict(self.state, available=self.available, enabled=self.enabled)

    def configure(self, enabled):
        if not self.available:
            raise RuntimeError('Apple Photos sync runs only in PhotoJournal on your Mac.')
        config = self.data / 'apple-sync.json'
        temporary = config.with_suffix('.tmp')
        temporary.write_text(json.dumps({'enabled': enabled}))
        temporary.replace(config)
        with self.lock:
            self.enabled = enabled
        if enabled:
            self.start()
            self.wake.set()

    def start(self):
        with self.lock:
            if self.thread is None or not self.thread.is_alive():
                self.thread = threading.Thread(target=self.loop, name='apple-photos-sync', daemon=True)
                self.thread.start()

    def loop(self):
        while True:
            self.wake.clear()
            if self.enabled:
                self.sync_once()
            self.wake.wait(600)

    def sync_once(self):
        with self.lock:
            self.state.update(running=True, error=None, imported=0, failed=0)
        imported = failed = 0
        error = None
        try:
            for identifier, day in recent_photos():
                if not self.enabled:
                    break
                source_id = 'apple:' + identifier
                if self.already_imported(source_id):
                    continue
                # Work in bounded batches; remaining photos are retried on the next scan.
                if imported + failed >= 50:
                    break
                try:
                    with tempfile.TemporaryDirectory(prefix='photojournal-export-') as directory:
                        photo = export_photo(identifier, Path(directory))
                        with photo.open('rb') as stream:
                            if self.ingest(stream, day, source_id=source_id, capture_day=day):
                                imported += 1
                except Exception:
                    failed += 1
        except Exception:
            error = ('Could not read Apple Photos. Open Photos, allow Terminal or Python to control Photos '
                     'when macOS asks, and try again. Permission is managed in System Settings → '
                     'Privacy & Security → Automation. Photos stored only in iCloud may need downloading first.')
        with self.lock:
            self.state.update(running=False, imported=imported, failed=failed, error=error,
                              last_checked=datetime.now(timezone.utc).isoformat())
