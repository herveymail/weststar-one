#!/bin/sh
# Nightly backup: database dump + uploaded files, kept 14 days. Run from the folder with docker-compose.yml.
#   crontab -e   →   30 2 * * *  cd /opt/weststar-one && ./deploy/backup.sh >> /var/log/weststar-backup.log 2>&1
# Copy the backups folder off this server too (another site / cloud bucket). Keep APP_ENCRYPTION_KEY
# somewhere safe and separate: without it the encrypted fields in a backup can't be read.
set -eu
DEST="${BACKUP_DIR:-./backups}"
STAMP=$(date +%Y-%m-%d_%H%M)
mkdir -p "$DEST"
umask 077
docker compose exec -T db sh -c 'mariadb-dump --single-transaction --routines --triggers -uroot -p"$MARIADB_ROOT_PASSWORD" weststar' | gzip > "$DEST/db_$STAMP.sql.gz"
docker compose exec -T app tar -C /data -czf - media > "$DEST/media_$STAMP.tar.gz"
find "$DEST" -name 'db_*.sql.gz' -mtime +14 -delete
find "$DEST" -name 'media_*.tar.gz' -mtime +14 -delete
echo "$(date) backup ok: $DEST/db_$STAMP.sql.gz"
