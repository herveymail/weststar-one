import time

from django.core.management.base import BaseCommand
from django.db import close_old_connections

from apps.core.jobs import run_due


class Command(BaseCommand):
    help = "Run background jobs that are due. --loop keeps running (jobs every minute; imports started in Settings within seconds)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--force", action="store_true", help="Run every job now")

    def handle(self, *args, loop=False, force=False, **opts):
        from apps.legacy.uploaded import process_queued

        last = 0.0
        while True:
            close_old_connections()
            if time.monotonic() - last >= 60 or not loop:
                last = time.monotonic()
                for name, result in run_due(force=force).items():
                    self.stdout.write(f"{name}: {result}")
            try:
                while process_queued():
                    pass
            except Exception as exc:  # noqa: BLE001 — keep the worker alive
                self.stderr.write(f"import: {exc}")
            if not loop:
                return
            time.sleep(5)
