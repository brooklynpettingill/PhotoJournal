# PhotoJournal

A local-first daily photo journal with square, white book pages inspired by the supplied Chatbooks reference.

## Run

```sh
cd /workspace/PhotoJournal
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

The server listens on loopback port 3000. Local development runs without authentication unless PHOTOJOURNAL_PASSWORD_HASH is set. Do not expose the development server to the public internet. The production entrypoint requires a password hash and persistent storage; see HOSTING.md. Set `PHOTOJOURNAL_DATA` to change the storage directory or `PORT` to change the port.

Upload JPEG, PNG, or WebP photographs in batches under 100 MB. EXIF capture dates determine each page; the chosen fallback date handles files without capture dates. Export HEIC to JPEG before importing. The first six images for a day are selected; edit a page to swap the selection, write a caption, and approve it. Changes to a page reset approval unless explicitly approved again. There is no automatic deletion.

Photos are saved as resized JPEGs (maximum 3000 pixels) in `data/photos`; captions, selection, and approvals live in `data/journal.sqlite3`. Keep your originals. Back up the whole data directory while the server is stopped. Uploaded photos remain on this machine; no AI service receives them.

Print preview uses browser printing with an 8-inch square page. It is a draft export, not a printer-certified PDF; inspect pagination and choose the matching paper size. Exact printer bleed, covers, color management, and binding still require integration and a proof copy.

## Validate

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check static/app.js
```

## Next integrations

Apple Photos automatic import is implemented for local Macs; see [APPLE_PHOTOS.md](APPLE_PHOTOS.md) for connection, permissions, limitations and ZIP update instructions. Its macOS bridge still needs on-device verification. Configure production authentication and HTTPS before external phone access. Add Google Takeout/Instagram archive import, deduplication, reliable date/timezone metadata, optional AI captions with explicit consent, and a printer-specific export. No hosting account, subscription, API key, or print order is needed for this version. Direct Google/cloud-library sync and AI captions are not implemented. Apple Photos imports run only while the local Mac app is open.

## Hosting

See [HOSTING.md](HOSTING.md) for the prepared Docker/Gunicorn deployment, private login, durable storage and backup checklist. Hosting and automated backups have not been provisioned.

## Mac Photos imports

Use **Photo sources → Connect Apple Photos** for automatic local scans of the last seven days, every ten minutes while the app runs. Your iPhone pictures must already be in Mac Photos via iCloud Photos or a cable import. This feature needs macOS Automation permission and an on-device test; see [APPLE_PHOTOS.md](APPLE_PHOTOS.md).

## iPhone imports without iCloud

Use **Photo sources → Enable iPhone uploads** for an opt-in, authenticated home-Wi-Fi receiver. See [IPHONE_SHORTCUT.md](IPHONE_SHORTCUT.md) for the free iPhone Shortcut and daily schedule. The Mac must be awake with the app running. Phone transfers use local HTTP on a trusted network; no cloud server or iCloud storage is needed. The iPhone Shortcut still requires on-device testing.

## Prewired iPhone Shortcut

[IPHONE_SHORTCUT.md](IPHONE_SHORTCUT.md) includes a local generator and in-app download buttons. Your Mac signs the file using Apple’s Shortcuts CLI; the cloud workspace cannot create an iCloud installation URL. Test the signed workflow on the iPhone before relying on automation. Personalized files contain your upload key and stay in ignored local data storage.
