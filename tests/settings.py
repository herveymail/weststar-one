"""Settings for the test run: safe throwaway keys, then the normal settings.
Uses the test_<DB_NAME> PostgreSQL database on the configured server."""
import base64
import os

os.environ["TESTING"] = "true"
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-0123456789-0123456789")
os.environ.setdefault("APP_ENCRYPTION_KEY", base64.b64encode(b"k" * 32).decode())
os.environ.setdefault("APP_URL", "http://testserver")
os.environ.setdefault("DB_PASSWORD", "ws_dev")

from weststar.settings import *  # noqa: E402,F403
