#!/usr/bin/env bash
# IQCG - PostgreSQL backup script (Linux / cron)
# Usage:
#   backup_db.sh daily    # keep 30
#   backup_db.sh hourly   # keep 48
set -euo pipefail

FREQUENCY="${1:-daily}"
PROJECT_DIR="${PROJECT_DIR:-/opt/iqcg}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/iqcg}"
KEEP_DAILY=30
KEEP_HOURLY=48

# --- read .env ---
set -a; source "$PROJECT_DIR/.env"; set +a

STAMP=$([[ "$FREQUENCY" == "daily" ]] && date +%F_%H%M || date +%F_%H00)
DIR="$BACKUP_ROOT/$FREQUENCY"
mkdir -p "$DIR"
OUT="$DIR/${DB_NAME}_${STAMP}.dump"

PGPASSWORD="$DB_PASSWORD" pg_dump -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" \
    -U "$DB_USER" -Fc -Z 6 -f "$OUT" "$DB_NAME"
echo "[$(date -Is)] OK: $OUT ($(du -h "$OUT" | cut -f1))"

KEEP=$([[ "$FREQUENCY" == "daily" ]] && echo "$KEEP_DAILY" || echo "$KEEP_HOURLY")
ls -1t "$DIR"/*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | while read -r f; do
    rm -f "$f"; echo "Retention: removed $(basename "$f")"
done
