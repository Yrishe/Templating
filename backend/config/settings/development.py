from __future__ import annotations

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Use SQLite for development ease; override with env vars for Postgres
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "management_dev"),  # noqa: F405
        "USER": os.environ.get("DB_USER", "postgres"),  # noqa: F405
        "PASSWORD": os.environ.get("DB_PASSWORD", "postgres"),  # noqa: F405
        "HOST": os.environ.get("DB_HOST", "localhost"),  # noqa: F405
        "PORT": os.environ.get("DB_PORT", "5432"),  # noqa: F405
    }
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ---------------------------------------------------------------------------
# Celery — eager in dev
# ---------------------------------------------------------------------------
#
# Run tasks synchronously inside the request so developers don't have to keep
# a `celery -A config worker` terminal running alongside `runserver`. Without
# this, `.delay()` calls push tasks to Redis and a missing worker silently
# swallows notifications / contract text extraction / Claude reply generation
# — the symptom is "I made a change and nothing shows up in the feed".
#
# `EAGER_PROPAGATES` means task exceptions bubble up as 500s instead of being
# logged and lost, which makes debugging broken tasks dramatically easier.
#
# Flip both off and run a real worker when you specifically want to test
# async behaviour (rate limits, retries, beat schedule).
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

SIMPLE_JWT = {  # noqa: F405
    **SIMPLE_JWT,  # noqa: F405
}

# Local dev runs over plain HTTP, so the refresh cookie can't set `Secure`
# (the browser would refuse to send it back). Production keeps the default.
REFRESH_COOKIE_SECURE = False

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Disable rate limiting in development
RATELIMIT_ENABLE = False

INSTALLED_APPS = INSTALLED_APPS + ["django_extensions"]  # noqa: F405

# Silence the django_extensions import error if not installed
try:
    import django_extensions  # noqa: F401
except ImportError:
    INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "django_extensions"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {"handlers": ["console"], "level": "DEBUG"},
}
