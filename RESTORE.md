# Emergency restore runbook

The production server snapshots `db.sqlite3` every minute into
`~/Sync/ddc-backup/` (`scripts/backup_db.sh`, run by the `ddc-backup.timer`
systemd user timer). Syncthing propagates that folder to the on-site laptop
and the mirror machine. If the server dies mid-tournament, the tournament
continues from the laptop on the venue LAN. Worst case: the last ~1 minute
of scores must be re-entered.

## Backup folder contents

- `db-latest.sqlite3` — consistent snapshot, at most ~1 minute old
- `db-YYYYMMDD-HHMM.sqlite3` — 10-minute history (kept 7 days), in case the
  latest snapshot contains a bad edit
- `env-backup` — copy of the server's `.env` (same `SECRET_KEY` keeps
  existing logins/sessions valid after restore)

## Prepare the laptop BEFORE the tournament (while connectivity is good)

1. Confirm `~/Sync/ddc-backup/db-latest.sqlite3` exists on the laptop and
   its timestamp keeps updating.
2. Clone and set up the app:

   ```bash
   git clone git@github.com:wilenius/ddc.git ~/git/ddc
   cd ~/git/ddc
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. Install `qrencode` (optional — gives a scannable QR code of the URL).
4. Do one full test restore (steps below) **with a phone on the same
   Wi-Fi/hotspot you'd use at the venue**: log in from the phone, check a
   tournament page renders. This also catches hotspots that isolate
   clients from each other. Then delete the test `db.sqlite3` and `.env`.

## Failover (server is dead)

On the laptop:

1. Copy in the newest snapshot (or a timestamped one if the latest looks
   wrong):

   ```bash
   cp ~/Sync/ddc-backup/db-latest.sqlite3 ~/git/ddc/db.sqlite3
   sqlite3 ~/git/ddc/db.sqlite3 "PRAGMA integrity_check;"   # expect: ok
   ```

2. Set up the environment:

   ```bash
   cp ~/Sync/ddc-backup/env-backup ~/git/ddc/.env
   ```

   Edit `~/git/ddc/.env`: set `DEBUG=True` and `ALLOWED_HOSTS=*`.
   (`DEBUG=True` makes runserver serve static files — fine for emergency
   LAN use.)

3. Put the laptop on the venue Wi-Fi / phone hotspot, then:

   ```bash
   ~/git/ddc/scripts/failover_serve.sh
   ```

   The script detects the LAN IP, opens the firewall for port 8000 if
   ufw/firewalld is active (asks for sudo), prints the URL to share —
   as a QR code if `qrencode` is installed — starts the server, and does
   a reachability sanity check. (`--url-only` prints just the URL/QR.)

4. Get the scorekeepers' phones onto the same hotspot, confirm the URL
   opens on one phone, and share it in the players' Signal group.

5. In the tournament's notification settings, disable Signal/email
   notifications — the laptop has no signal-cli daemon, so sends would just
   fail in the background.

## Server-side installation (already done on prod)

```bash
cp scripts/ddc-backup.service scripts/ddc-backup.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now ddc-backup.timer
```
