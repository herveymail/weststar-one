"""Test settings: safe throwaway keys; uses the test_<DB_NAME> database on the configured MariaDB."""
import base64
import os

os.environ["TESTING"] = "true"
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-0123456789-0123456789")
os.environ.setdefault("APP_ENCRYPTION_KEY", base64.b64encode(b"k" * 32).decode())
os.environ.setdefault("APP_URL", "http://testserver")
