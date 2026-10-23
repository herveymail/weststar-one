#!/bin/sh
# Bring everything over from the old PHP Weststar One.
#
#   ./deploy/import-old.sh /path/to/old-dump.sql[.gz] [/path/to/old/uploads] [--dry-run]
#
# Loads the old dump into a temporary MariaDB container (your live old server is never touched),
# runs the importer into PostgreSQL, then removes the temporary database. Safe to run again: it
# updates instead of duplicating and never overwrites what you've changed in the new app.
# Old keys come from .env: OLD_APP_KEY and OLD_ENCRYPTION_KEY (the wizard fills these in).
set -eu
cd "$(dirname "$0")/.."
DUMP="$1"; shift
UPLOADS=""
if [ "${1:-}" ] && [ "${1#--}" = "$1" ]; then UPLOADS="$1"; shift; fi
. ./.env
cleanup() { docker compose --profile import rm -sf olddb >/dev/null 2>&1 || true; }
trap cleanup EXIT
echo "Starting a temporary database for the old data…"
docker compose --profile import up -d --wait olddb
echo "Loading $DUMP…"
case "$DUMP" in *.gz) CAT="gunzip -c" ;; *) CAT="cat" ;; esac
# Some dumps carry options a fresh server doesn't have (sandbox marker, ENCRYPTED=YES tables).
$CAT "$DUMP" | sed -e '1{/enable the sandbox mode/d}' -e 's/ `ENCRYPTED`=YES//g' \
  | docker compose --profile import exec -T olddb sh -c 'mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" myflow_old'
MOUNT=""; UPL=""
if [ -n "$UPLOADS" ]; then
  MOUNT="-v $(cd "$UPLOADS" && pwd):/old-uploads:ro"
  UPL="--uploads /old-uploads"
fi
# shellcheck disable=SC2086
docker compose run --rm -T $MOUNT -e OLD_APP_KEY="${OLD_APP_KEY:-}" -e OLD_ENCRYPTION_KEY="${OLD_ENCRYPTION_KEY:-}" app \
  python manage.py import_legacy --mysql "mysql://importer:${DB_PASSWORD}@olddb:3306/myflow_old" $UPL "$@"
