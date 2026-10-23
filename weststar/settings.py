"""
Weststar ONE — Django settings.

Everything that differs between servers comes from environment variables (or a .env file next to
manage.py). The app refuses to start without a real SECRET_KEY and APP_ENCRYPTION_KEY — the old PHP
app silently fell back to a built-in default key, which is exactly what we don't want.
"""
import base64
import os
from pathlib import Path
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


_load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"Set {name} in the environment or in .env (see .env.example).")
    return value or ""


def env_bool(name: str, default: bool = False) -> bool:
    return env(name, "true" if default else "false").lower() in ("1", "true", "yes", "on")


DEBUG = env_bool("DEBUG", False)
TESTING = env_bool("TESTING", False)

SECRET_KEY = env("SECRET_KEY", required=True)
if len(SECRET_KEY) < 40:
    raise ImproperlyConfigured("SECRET_KEY must be at least 40 random characters (python -c \"import secrets; print(secrets.token_urlsafe(50))\").")

# 32 random bytes, base64. Encrypts 2FA seeds, Wi-Fi passwords, H/R SSN/bank fields, secret settings.
APP_ENCRYPTION_KEY = env("APP_ENCRYPTION_KEY", required=True)
try:
    if len(base64.b64decode(APP_ENCRYPTION_KEY)) != 32:
        raise ValueError
except Exception as exc:  # noqa: BLE001
    raise ImproperlyConfigured("APP_ENCRYPTION_KEY must be 32 bytes, base64 encoded (openssl rand -base64 32).") from exc
# Older keys, still accepted for decrypting while a key is being rotated (comma separated).
APP_ENCRYPTION_KEYS_OLD = [k.strip() for k in env("APP_ENCRYPTION_KEYS_OLD").split(",") if k.strip()]

# The address people type in their browser, e.g. https://one.weststarmsp.com
APP_URL = env("APP_URL", "http://localhost:8000").rstrip("/")
_app = urlparse(APP_URL)
HTTPS = _app.scheme == "https"
ALLOWED_HOSTS = [h.strip() for h in env("ALLOWED_HOSTS", _app.hostname or "localhost").split(",") if h.strip()]
if DEBUG or TESTING:
    ALLOWED_HOSTS += ["localhost", "127.0.0.1", "testserver"]
CSRF_TRUSTED_ORIGINS = [f"{_app.scheme}://{_app.netloc}"]
# Optional own address for the client portal (e.g. https://portal.weststarmsp.com). Otherwise APP_URL/client-portal/.
PORTAL_URL = env("PORTAL_URL", "").rstrip("/")
if PORTAL_URL:
    _p = urlparse(PORTAL_URL)
    ALLOWED_HOSTS.append(_p.hostname)
    CSRF_TRUSTED_ORIGINS.append(f"{_p.scheme}://{_p.netloc}")
PORTAL_BASE = (PORTAL_URL or APP_URL) + "/client-portal"

# Behind Caddy/nginx: trust exactly one proxy hop for the client IP and the https flag.
TRUST_PROXY = env_bool("TRUST_PROXY", False)
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "apps.core",
    "apps.accounts",
    "apps.crm",
    "apps.helpdesk",
    "apps.sales",
    "apps.billing",
    "apps.tools",
    "apps.hr",
    "apps.files",
    "apps.portal",
    "apps.legacy",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.SessionGuardMiddleware",
    "apps.portal.auth.PortalSessionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "weststar.urls"
WSGI_APPLICATION = "weststar.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context.app_context",
            ],
        },
    },
]

DATABASES = {
    "default": {
        # PostgreSQL. (The old PHP app's MariaDB is only ever read by the importer, see apps/legacy.)
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "weststar"),
        "USER": env("DB_USER", "weststar"),
        "PASSWORD": env("DB_PASSWORD", required=True),
        "HOST": env("DB_HOST", "127.0.0.1"),
        "PORT": env("DB_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {"sslmode": env("DB_SSLMODE", "prefer")},
        "TEST": {"NAME": env("DB_TEST_NAME", "test_weststar")},
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CACHES = {"default": {"BACKEND": "django.core.cache.backends.db.DatabaseCache", "LOCATION": "cache_table"}}

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "/login/"
# Argon2id for everyone. BCrypt stays listed only so passwords imported from the old PHP app still work;
# Django re-hashes them to Argon2 the first time each person signs in.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.BCryptPasswordHasher",
]
if TESTING:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher", *PASSWORD_HASHERS]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Sessions: database-backed, HttpOnly cookie, 12 hours max; idle timeout enforced in SessionGuardMiddleware.
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_NAME = "__Host-ws_session" if HTTPS else "ws_session"
SESSION_COOKIE_SECURE = HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 12 * 3600
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_NAME = "__Host-ws_csrf" if HTTPS else "ws_csrf"
CSRF_COOKIE_SECURE = HTTPS
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
if HTTPS and not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]  # container health check talks plain HTTP inside the network
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

DATA_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "America/Denver")
USE_I18N = False
USE_TZ = True

# Uploaded files. Never served directly: downloads go through an access-checked view.
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
MEDIA_URL = "/files-not-served-directly/"
MAX_UPLOAD_MB = int(env("MAX_UPLOAD_MB", "25"))
FILE_UPLOAD_MAX_MEMORY_SIZE = 3 * 1024 * 1024
# Large uploads (e.g. the old backup in Settings › Import) are spooled to disk next to the files,
# not to /tmp (which is in memory inside the container).
# (deploy/entrypoint.sh creates the folder when the container starts; without it, the system default is used.)
FILE_UPLOAD_TEMP_DIR = str(MEDIA_ROOT / ".upload-tmp") if (MEDIA_ROOT / ".upload-tmp").is_dir() else None
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Static files are public (CSS/JS/icons): readable by everyone in the container, unlike uploads,
    # which use the stricter FILE_UPLOAD_* permissions below.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if not (DEBUG or TESTING) else "django.contrib.staticfiles.storage.StaticFilesStorage",
                    "OPTIONS": {"file_permissions_mode": 0o644, "directory_permissions_mode": 0o755}},
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}

# ── App behaviour ──
LOGIN_LOCK_AFTER = 5          # failed passwords (or 2FA codes) before the account locks
LOGIN_LOCK_MINUTES = 15       # first lock; doubles each further time
LOGIN_IP_MAX_FAILS = 30       # failed sign-ins from one IP in 15 minutes before that IP is blocked
