import time

from django.core.management.base import BaseCommand

from apps.core.jobs import run_due


class Command(BaseCommand):
    help = "Run background jobs that are due. --loop keeps running (checks every minute)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--force", action="store_true", help="Run every job now")

    def handle(self, *args, loop=False, force=False, **opts):
        while True:
            results = run_due(force=force)
            for name, result in results.items():
                self.stdout.write(f"{name}: {result}")
            if not loop:
                return
            time.sleep(60)
