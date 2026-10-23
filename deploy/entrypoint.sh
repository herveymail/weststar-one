#!/bin/sh
# web  — apply database migrations, then serve the app with gunicorn
# jobs — run the background jobs loop (SLA watch, recurring invoices, overdue, auto-close, cleanup)
# anything else — run it (e.g. "python manage.py import_legacy …")
set -e
case "$1" in
  web)
    python manage.py migrate --noinput
    python manage.py createcachetable
    exec gunicorn weststar.wsgi:application --bind 0.0.0.0:8000 --workers "${WEB_WORKERS:-3}" --timeout 120 \
      --forwarded-allow-ips="*" --access-logfile - --max-requests 2000 --max-requests-jitter 200
    ;;
  jobs)
    exec python manage.py run_jobs --loop
    ;;
  *)
    exec "$@"
    ;;
esac
