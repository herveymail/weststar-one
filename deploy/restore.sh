#!/bin/sh
# Restore a backup made by backup.sh (REPLACES the current data).
#   ./deploy/restore.sh backups/db_2026-10-23_0230.dump [backups/media_2026-10-23_0230.tar.gz]
set -eu
cd "$(dirname "$0")/.."
DB="$1"; MEDIA="${2:-}"
printf "This replaces ALL current data with %s. Type RESTORE to continue: " "$DB"; read -r ok
[ "$ok" = "RESTORE" ] || { echo "Cancelled."; exit 1; }
docker compose stop app jobs
docker compose exec -T db pg_restore -U weststar -d weststar --clean --if-exists --no-owner < "$DB"
if [ -n "$MEDIA" ]; then docker compose run --rm -T --entrypoint sh app -c "rm -rf /data/media/* && tar -C /data -xzf -" < "$MEDIA"; fi
docker compose start app jobs
echo "Restored."
