"""Set app settings from the install wizard (or a script) without using the web page.

    echo '{"company.name": "Weststar MSP", "google.client_secret": "…"}' | python manage.py configure

Values are read from standard input as JSON, so secrets never appear in the process list or shell
history. Only keys that exist in Settings are accepted; secret fields are stored encrypted.
"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError

from apps.core.models import Setting
from apps.core.settings_catalog import ALL_FIELDS


class Command(BaseCommand):
    help = "Set settings from JSON on standard input."

    def handle(self, *args, **o):
        try:
            data = json.load(sys.stdin)
        except ValueError as e:
            raise CommandError(f"Expected JSON on standard input: {e}") from e
        if not isinstance(data, dict):
            raise CommandError("Expected a JSON object of setting: value pairs.")
        for key, value in data.items():
            spec = ALL_FIELDS.get(key)
            if spec is None:
                raise CommandError(f"Unknown setting: {key}")
            value = "" if value is None else str(value)
            if spec["type"] == "select" and value and value not in spec["options"]:
                raise CommandError(f"{key}: must be one of {', '.join(spec['options'])}")
            if spec["type"] == "secret" and not value:
                continue
            Setting.put(key, value[:20000], secret=spec["type"] == "secret")
            self.stdout.write(f"  set {key}" + (" (encrypted)" if spec["type"] == "secret" else ""))
