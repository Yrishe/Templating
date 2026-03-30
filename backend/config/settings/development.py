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

SIMPLE_JWT = {  # noqa: F405
    **SIMPLE_JWT,  # noqa: F405
    "AUTH_COOKIE_SECURE": False,
}

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
