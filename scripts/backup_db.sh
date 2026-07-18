#!/usr/bin/env bash
# Snapshot the DDC sqlite database into the Syncthing folder so an on-site
# laptop always has a fresh copy to restore from. See RESTORE.md.
set -euo pipefail

DB="$HOME/git/ddc/db.sqlite3"
ENV_FILE="$HOME/git/ddc/.env"
DEST="$HOME/Sync/ddc-backup"
# Staging lives outside ~/Sync so Syncthing can never ship a half-written file.
STAGING="$HOME/.cache/ddc-backup"

mkdir -p "$DEST" "$STAGING"

# .backup takes proper sqlite locks, so the copy is consistent even while
# gunicorn workers are writing scores (WAL mode). The rename into ~/Sync is
# atomic (same filesystem).
sqlite3 "$DB" ".backup '$STAGING/db-latest.sqlite3'"
mv "$STAGING/db-latest.sqlite3" "$DEST/db-latest.sqlite3"

# Same SECRET_KEY on the restore machine keeps existing logins valid.
if ! cmp -s "$ENV_FILE" "$DEST/env-backup"; then
    cp "$ENV_FILE" "$DEST/env-backup"
fi

# Timestamped copy every 10 minutes, pruned after 7 days, in case the latest
# snapshot ever contains a mistake worth stepping back from.
if (( 10#$(date +%M) % 10 == 0 )); then
    cp "$DEST/db-latest.sqlite3" "$DEST/db-$(date +%Y%m%d-%H%M).sqlite3"
    find "$DEST" -name 'db-2*.sqlite3' -mtime +7 -delete
fi
