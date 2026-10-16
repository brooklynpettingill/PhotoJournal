"""Run on your own computer; paste the output into the host's secret settings."""
from getpass import getpass
from werkzeug.security import generate_password_hash

password = getpass('Choose your journal password (at least 16 characters): ')
if len(password) < 16:
    raise SystemExit('Use at least 16 characters.')
if password != getpass('Repeat password: '):
    raise SystemExit('Passwords did not match.')
print(generate_password_hash(password))
