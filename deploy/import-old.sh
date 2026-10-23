#!/bin/sh
# Bring everything over from the old PHP Weststar One.
#
#   ./deploy/import-old.sh /path/to/old-dump.sql.gz /path/to/old/uploads [--dry-run]
#
# Loads the old dump into a separate "myflow_old" database inside the db container (your live old
# server is never touched), then runs the importer. Safe to run again: it updates instead of duplicating.
# Put OLD_APP_KEY and OLD_ENCRYPTION_KEY (from the old config/config.php) in .env first.
set -eu
DUMP="$1"; UPLOADS="${2:-}"; shift 1; [ -n "$UPLOADS" ] && shift 1 || true
. ./.env
echo "Loading $DUMP into myflow_old…"
docker compose exec -T db sh -c "mariadb -uroot -p\"\$MARIADB_ROOT_PASSWORD\" -e \"DROP DATABASE IF EXISTS myflow_old; CREATE DATABASE myflow_old CHARACTER SET utf8mb4; GRANT SELECT ON myflow_old.* TO 'weststar'@'%';\""
case "$DUMP" in *.gz) CAT="gunzip -c" ;; *) CAT="cat" ;; esac
# Drop MariaDB-11.x-only bits some dumps carry (sandbox marker, ENCRYPTED=YES table option).
$CAT "$DUMP" | sed -e '1{/enable the sandbox mode/d}' -e 's/ `ENCRYPTED`=YES//g' \
  | docker compose exec -T db sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" myflow_old'
MOUNT=""; UPL=""
if [ -n "$UPLOADS" ]; then
  MOUNT="-v $(cd "$UPLOADS" && pwd):/old-uploads:ro"
  UPL="--uploads /old-uploads"
fi
# shellcheck disable=SC2086
docker compose run --rm -T $MOUNT -e OLD_APP_KEY="${OLD_APP_KEY:-}" -e OLD_ENCRYPTION_KEY="${OLD_ENCRYPTION_KEY:-}" app \
  python manage.py import_legacy --mysql "mysql://weststar:${DB_PASSWORD}@db:3306/myflow_old" $UPL "$@"
