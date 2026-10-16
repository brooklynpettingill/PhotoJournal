# Automatic daily imports on your Mac (no subscription)

PhotoJournal can check Apple Photos on the same Mac every ten minutes while the app is running. It scans the last seven days, copies new pictures into daily draft pages, and remembers Apple asset IDs so subsequent scans skip completed imports. This is a Mac-only bridge using Apple's built-in Photos scripting and sips JPEG conversion. It does not log into iCloud or Google, and never changes or deletes your source pictures.

The library bridge must still be validated on your Mac. Automated tests exercise parsing, ingestion, date assignment, duplicate handling, permission failures, and unsupported platforms with mocked Photos exports; they do not prove compatibility with your particular macOS or iCloud setup.

## Before connecting

Open Photos on your Mac and confirm recent iPhone photos are visible. If you already use iCloud Photos, check that your Mac and iPhone use the same Apple Account and that syncing is enabled on both. iCloud's free storage allowance may not hold a full library; buying storage is not required by this app. If your free space is full, use a cable to import photos from your unlocked iPhone into Mac Photos instead. Cable imports are manual; the journal scan can then run automatically.

Allow originals to download locally before the first test. If an original lives only in iCloud, opening/downloading it in Photos may be necessary; export attempts can fail while offline. Only still images are imported. Live Photo videos and ordinary videos are skipped. HEIC/HEIF photos are converted using macOS sips. These are downsized journal copies, not a backup of your original library.

## Connect

1. Start PhotoJournal using `.venv/bin/python app.py` and open it in your Mac browser.
2. Open **Photo sources**, then **Connect Apple Photos**.
3. macOS may open Photos and ask whether Terminal or Python may control it. Allow this for the import. If denied, check **System Settings → Privacy & Security → Automation**, then retry. Labels and permission behavior can vary by macOS version.
4. Keep the app running. The status reports the last scan, imported count, and any failed exports. Refresh the book or select the relevant year to see imported days. Imported captions are blank for you to write; AI captions are not implemented.
5. Open a sample day and confirm it matches the capture date in Photos. Verify that a second scan does not duplicate the pictures. Then try another new photo.

Use **Pause imports** to stop future scans. An export already in progress may finish. Connection preference persists in `data/apple-sync.json`; restarting PhotoJournal resumes scans if enabled. Nothing runs when PhotoJournal is stopped or the Mac sleeps; it catches up within the seven-day window on the next scan. It processes at most 50 unimported items per scan. Missing or unreadable originals are retried later. Older history, source edits after import, and date changes are not synchronized automatically. Photos imported manually and again from Apple Photos are not yet deduplicated across sources.

## Update an earlier ZIP download

Stop the running app with Control+C. From the PhotoJournal directory in Terminal, download and run the updater:

```sh
curl -fL https://raw.githubusercontent.com/brooklynpettingill/PhotoJournal/main/tools/update_mac.py -o /tmp/photojournal-update.py && .venv/bin/python /tmp/photojournal-update.py
.venv/bin/python -m pip install -r requirements.txt && .venv/bin/python app.py
```

The updater downloads the project's GitHub ZIP over verified HTTPS, updates only a fixed list of application files, and saves overwritten code in `.updates-backup`. It never replaces `data/` or `.venv/`. Keep your original photo libraries and normal Mac backups.

## Google Photos

A Google login alone does not grant unattended access to the entire personal library under Google's current Photos API model. Picker sessions require the user to choose the media. No Google login or unofficial scraping is added here. Google Takeout archives could support a separate historical-import workflow, but are not implemented by this feature. If a picture exists only in Google Photos, it will not appear in the Mac Photos importer unless you first save/import it into Apple Photos.
