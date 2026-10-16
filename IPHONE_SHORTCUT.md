# Free daily iPhone imports, without iCloud Photos

Your iPhone can push photos to PhotoJournal on your Mac using Apple's free Shortcuts app. No cloud account, subscription, or iCloud storage is required. This is a local home-Wi-Fi workflow: the Mac must be awake, PhotoJournal must be running, and both devices must be able to reach each other on the same trusted home network at the scheduled time. Guest networks may isolate devices. It is not an always-on cloud sync.

The receiver's authentication, upload, duplicate protection, storage and start/stop behavior are tested locally. The iPhone Shortcut and macOS permission behavior still require a real-device trial; an unattended daily run is not confirmed until that trial succeeds.

## Update and pair the Mac

Stop the running app with Control+C. From your PhotoJournal folder in Terminal:

```sh
curl -fL https://raw.githubusercontent.com/brooklynpettingill/PhotoJournal/main/tools/update_mac.py -o /tmp/photojournal-update.py && .venv/bin/python /tmp/photojournal-update.py
.venv/bin/python -m pip install -r requirements.txt && .venv/bin/python app.py
```

The updater preserves `data/` and `.venv/`, and backs up overwritten application files. Refresh the browser, open **Photo sources**, and choose **Enable iPhone uploads**. Allow macOS Local Network/incoming-connection permission for Python if prompted. The app displays a Wi-Fi upload address and a private upload key. Copy the key only into your Shortcut; do not include it in screenshots or send it in chat.

The normal journal still binds only to loopback port 3000. A separate upload-only receiver listens on port 3002 after you enable it. It serves no photos, pages or login interface. Uploads require the private key; internet-origin requests and browser cross-site requests are rejected. **Local transfers use HTTP, so the photos and key are not encrypted on the Wi-Fi network. Use only a trusted home network; never forward port 3002 on the router.** Stop the receiver when it is not wanted. The setting and private key persist locally, so starting PhotoJournal restores an enabled receiver. If the Mac's Wi-Fi IP changes, update the Shortcut URL.

## Build and test a Shortcut on the iPhone

Labels may differ by iOS version. Begin with a single photo and a manual run, then expand to daily automation.

1. Open **Shortcuts**, tap **+**, and name it **Daily PhotoJournal**.
2. Add **Find Photos**. Filter **Date Taken** to **in the last 2 days**, and **Media Type** to **Image**. For the first test, turn **Limit** on and set it to **1**.
3. Add **Repeat with Each** using the photos returned by Find Photos.
4. Inside the repeat, add **Get Details of Images**, choose **Date Taken**, and set its input to **Repeat Item**. Add **Format Date**, using a **Custom** format of `yyyy-MM-dd`. This is the date header for the upload, not a caption.
5. Add **Convert Image**, select **JPEG**, and explicitly set its input to the original **Repeat Item**. Do not let it use the Formatted Date from the preceding action. For unusually large images, optionally resize before converting.
6. Add **Get Contents of URL** with the upload address shown on your Mac. Expand its options:
   - Method: **POST**
   - Request Body: **File**
   - File: **Converted Image**
   - Header `Authorization`: the word `Bearer`, a space, then your private upload key
   - Header `X-Photo-Date`: insert the **Formatted Date** variable
   - Header `Content-Type`: `image/jpeg`
7. Ensure all the actions above are inside **Repeat**, before **End Repeat**. Run it manually while PhotoJournal is open on the awake Mac. Allow Photos and local-network access when asked. The response should have `imported: true` (or `duplicate: true` for a repeat).
8. Refresh PhotoJournal or leave Photo sources open (it refreshes every 15 seconds). Select the relevant year and confirm the photo appears on its correct date. Rerun the Shortcut: the same decoded image on the same capture date should be skipped. Different crops, resizing or compression can produce different pixels and may be imported again.

## Schedule it

After the one-photo test succeeds, turn off **Limit** in Find Photos. In **Shortcuts → Automation**, create a **Time of Day** personal automation, choose Daily PhotoJournal, and choose **Run Immediately** if offered. On older iOS versions the equivalent setting may be **Ask Before Running** turned off. Pick a time when the Mac will be awake and both devices are home. Confirm a real scheduled run, including its Photos and local-network permissions; iOS may require unlocking or additional permission depending on the actions/version.

The last-two-days window provides basic catch-up after one missed run. A sleeping Mac, a stopped app, being away from home, or a denied permission prevents delivery. Keep the originals on your phone. For longer missed periods, widen the Find Photos date filter and run manually; do not assume Shortcuts queues failed uploads automatically. Each photo must be under 25 MB. Videos are skipped; Live Photo motion is not included.

The first six photos on a day are selected for that page; others remain available for swapping. New imports reset that day's approval. Captions remain manual. Existing uploads from other sources are not deduplicated against phone uploads yet.

## Pause or disconnect

Use **Stop iPhone uploads** in Photo sources and disable the iPhone automation. Your existing photos and captions stay saved. An upload already in progress may finish. If the key is accidentally exposed, stop uploads, quit PhotoJournal, remove only `data/iphone-receiver.json`, restart and enable uploads to generate a new key, then update the Shortcut.
