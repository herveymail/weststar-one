"""Import everything from the old PHP Weststar One.

    python manage.py import_legacy --old-config /var/www/myflow/config/config.php [--dry-run]
    python manage.py import_legacy --mysql mysql://user:pass@host:3306/myflow [--dry-run]
          (old keys from the OLD_APP_KEY / OLD_ENCRYPTION_KEY environment variables)

--old-config reads DB_HOST, DB_USER, DB_PASS, DB_NAME, APP_KEY and ENCRYPTION_KEY straight from the old
config file, so secrets never go on the command line (where they'd end up in shell history).
"""
import os
from urllib.parse import unquote, urlparse

import MySQLdb
from django.core.management.base import BaseCommand, CommandError

from apps.legacy.crypto import parse_old_config
from apps.legacy.importer import Importer


class Command(BaseCommand):
    help = "Copy tickets, clients, billing, H/R and everything else from the old PHP Weststar One."

    def add_arguments(self, p):
        p.add_argument("--old-config", help="Path to the old app's config/config.php")
        p.add_argument("--mysql", help="mysql://user:pass@host:3306/dbname (if not using --old-config)")
        p.add_argument("--uploads", help="The old app's uploads/ folder (ticket attachments, client and project files)")
        p.add_argument("--dry-run", action="store_true", help="Do everything, then roll it back. Nothing is saved.")

    def handle(self, *args, **o):
        cfg = {}
        if o["old_config"]:
            try:
                with open(o["old_config"], encoding="utf-8") as fh:
                    cfg = parse_old_config(fh.read())
            except OSError as e:
                raise CommandError(f"Can't read {o['old_config']}: {e}") from e
        if o["mysql"]:
            u = urlparse(o["mysql"])
            conn_args = {"host": u.hostname or "localhost", "port": u.port or 3306, "user": unquote(u.username or ""),
                         "password": unquote(u.password or ""), "database": u.path.lstrip("/")}
        elif cfg:
            host, _, port = cfg.get("DB_HOST", "localhost").partition(":")
            conn_args = {"host": host, "port": int(port or 3306), "user": cfg.get("DB_USER", ""), "password": cfg.get("DB_PASS", ""), "database": cfg.get("DB_NAME", "")}
        else:
            raise CommandError("Pass --old-config /path/to/old/config/config.php, or --mysql mysql://user:pass@host/db")
        if o["uploads"] and not os.path.isdir(o["uploads"]):
            raise CommandError(f"Uploads folder not found: {o['uploads']}")
        app_key = os.environ.get("OLD_APP_KEY") or cfg.get("APP_KEY", "")
        enc_key = os.environ.get("OLD_ENCRYPTION_KEY") or cfg.get("ENCRYPTION_KEY", "")
        if not app_key or not enc_key:
            self.stderr.write("⚠  Old APP_KEY / ENCRYPTION_KEY not given — 2FA seeds, Wi-Fi passwords and H/R secrets will be skipped.")
        try:
            conn = MySQLdb.connect(charset="utf8mb4", use_unicode=True, connect_timeout=15, **conn_args)
        except MySQLdb.Error as e:
            raise CommandError(f"Can't connect to the old database: {e}") from e
        try:
            run = Importer(conn, app_key, enc_key, log=self.stdout.write, uploads_dir=o["uploads"]).run(dry_run=o["dry_run"])
        finally:
            conn.close()
        warnings = [f"{s['name']}: {w}" for s in run.summary for w in s["warnings"]]
        self.stdout.write(f"\n{'DRY RUN — nothing was saved.' if o['dry_run'] else 'Import finished.'} Run #{run.pk}, {run.total} records.")
        if warnings:
            self.stdout.write(f"\n{len(warnings)} warning(s):")
            for w in warnings[:50]:
                self.stdout.write("  - " + w)
            if len(warnings) > 50:
                self.stdout.write(f"  … and {len(warnings) - 50} more (see Settings › Import)")
