#!/usr/bin/env bash
# Nightly database backup (run from cron on the host). Keeps 14 days.
# Copy the files somewhere off the server too (Wasabi, S3 …) — and keep APP_ENCRYPTION_KEY with them, offline.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
docker compose exec -T db pg_dump -U weststar --format=custom weststar > "backups/weststar-$stamp.dump"
find backups -name 'weststar-*.dump' -mtime +14 -delete
echo "backups/weststar-$stamp.dump"
