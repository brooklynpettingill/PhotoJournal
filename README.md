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

Test a real iPhone Shortcut upload workflow; configure production authentication and HTTPS before external phone access. Add Google Takeout/Instagram archive import, deduplication, reliable date/timezone metadata, optional AI captions with explicit consent, and a printer-specific export. No hosting account, subscription, API key, or print order is needed for this version. Automated cloud sync and AI captions are not implemented.

## Hosting

See [HOSTING.md](HOSTING.md) for the prepared Docker/Gunicorn deployment, private login, durable storage and backup checklist. Hosting and automated backups have not been provisioned.
