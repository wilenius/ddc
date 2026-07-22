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

# Timestamped copy every 10 minutes. Keep all of today's snapshots (the real
# recovery window — a tournament-day failure is noticed within the hour) plus
# the single newest snapshot from yesterday as a hedge against a bad "latest".
# Everything older is pruned. Long-term backups are a separate concern.
if (( 10#$(date +%M) % 10 == 0 )); then
    cp "$DEST/db-latest.sqlite3" "$DEST/db-$(date +%Y%m%d-%H%M).sqlite3"

    today=$(date +%Y%m%d)
    keep_yesterday=$(ls "$DEST"/db-"$(date -d yesterday +%Y%m%d)"-*.sqlite3 2>/dev/null | sort | tail -1 || true)
    for f in "$DEST"/db-2*.sqlite3; do
        [ -e "$f" ] || continue
        case "$f" in
            "$DEST"/db-"$today"-*.sqlite3) ;;   # keep all of today
            "$keep_yesterday") ;;               # keep one from yesterday
            *) rm -f "$f" ;;
        esac
    done
fi
