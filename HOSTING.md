# Private hosting checklist

This package is prepared for a single owner. Hosting has not been purchased or deployed. Environment publication preserves development state; it does not deploy this website or push code to GitHub.

## Suggested first host: Render

Use a paid Docker web service with a persistent disk. Do not use an ephemeral free instance for your photo collection. Check current pricing for both the service and disk before confirming purchase. No account, charge, or service has been created by this project.

1. Create a Render account using your GitHub account. The project must first be committed and pushed to your PhotoJournal repository; the current development files have not been pushed. Keep the repository private if preferred. Never commit data/, .venv/, or credentials.
2. Create a Docker web service from that repository, with the repository root as the build context. The Dockerfile starts Gunicorn and honors the host's PORT variable.
3. Add a persistent disk mounted at `/data` (start with at least 10 GB; monitor usage). Set `PHOTOJOURNAL_DATA=/data`. Disk ownership must allow UID 10001 to write there; check the deployment log and resolve permissions before uploading real photos. Run one instance; do not enable replicas with SQLite/local storage.
4. Set `PHOTOJOURNAL_USERNAME` to your chosen username. Generate a password hash on your own computer using `python tools/password_hash.py` after installing the dependencies. Enter only its output into the host's secret environment variable `PHOTOJOURNAL_PASSWORD_HASH`. Keep your chosen password in a password manager. Do not paste it into chat. The production entrypoint refuses startup without a password hash and absolute data path.
5. Set the health-check path to `/healthz`. Use the host's HTTPS address exclusively. Open it on your phone and enter your username and password when the browser prompts. This version uses the browser's Basic login prompt; close the private browsing session to clear its cached login. No password recovery, per-user accounts, or shared family access is implemented.
6. Test with non-sensitive photos first. Import photos, edit a caption, approve a page, and restart the service. Confirm photographs and captions survived. Confirm an incognito window requests login and cannot fetch private photos without authentication.
7. Before importing your library, arrange an independent backup. Stop the service and copy the entire persistent `/data` directory (database and photos) to a separate private destination. Restore that copy into a separate test instance and verify pages and photographs before relying on the backup. Host snapshots alone are not an independent backup. Automated remote backups are not configured yet.

If this service cannot attach durable storage or cannot write to the disk, stop setup before uploading personal photos. Keep your original Apple/Google libraries. This app stores downsized copies and is not a replacement for your photo backup.

## Local production validation

Set PHOTOJOURNAL_PASSWORD_HASH, PHOTOJOURNAL_USERNAME, and an absolute PHOTOJOURNAL_DATA in the process environment, then run:

```sh
.venv/bin/gunicorn --bind 127.0.0.1:3001 --workers 1 --threads 4 --timeout 120 wsgi:app
```

HTTP is acceptable only on loopback for testing. An HTTPS-terminating host is required for external access. Never expose the development server from app.py.
