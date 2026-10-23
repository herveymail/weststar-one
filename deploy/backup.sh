#!/bin/sh
# Backup: PostgreSQL dump + uploaded files, kept 14 days, optionally copied to Wasabi/S3.
# The install wizard adds this to cron (nightly). Run it from the Weststar ONE folder.
# Keep APP_ENCRYPTION_KEY somewhere safe and separate: without it the encrypted fields in a backup can't be read.
set -eu
cd "$(dirname "$0")/.."
[ -f .env ] && . ./.env
DEST="${BACKUP_DIR:-./backups}"
STAMP=$(date +%Y-%m-%d_%H%M)
mkdir -p "$DEST"
umask 077
docker compose exec -T db pg_dump -U weststar -d weststar --format=custom --no-owner > "$DEST/db_$STAMP.dump"
docker compose exec -T app tar -C /data -czf - media > "$DEST/media_$STAMP.tar.gz"
find "$DEST" -name 'db_*.dump' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
find "$DEST" -name 'media_*.tar.gz' -mtime +"${BACKUP_KEEP_DAYS:-14}" -delete
# Off-site copy (Wasabi or any S3), if configured by the wizard.
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
  docker run --rm -v "$(cd "$DEST" && pwd)":/backups:ro \
    -e AWS_ACCESS_KEY_ID="$BACKUP_S3_KEY" -e AWS_SECRET_ACCESS_KEY="$BACKUP_S3_SECRET" -e AWS_DEFAULT_REGION="${BACKUP_S3_REGION:-us-east-1}" \
    amazon/aws-cli:2.27.0 s3 sync /backups "s3://$BACKUP_S3_BUCKET/${BACKUP_S3_PREFIX:-weststar-one}/" \
    --endpoint-url "${BACKUP_S3_ENDPOINT:-https://s3.us-east-1.wasabisys.com}" --only-show-errors
fi
echo "$(date) backup ok: $DEST/db_$STAMP.dump"
