from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("management")

# Use Django settings with the CELERY_ namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all INSTALLED_APPS
app.autodiscover_tasks()

# ── Periodic task schedule (Celery beat) ─────────────────────────────────
app.conf.beat_schedule = {
    "check-upcoming-deadlines-daily": {
        "task": "notifications.tasks.check_upcoming_deadlines",
        "schedule": crontab(hour=8, minute=0),
    },
    "check-unresolved-email-occurrences-daily": {
        "task": "notifications.tasks.check_unresolved_email_occurrences",
        "schedule": crontab(hour=9, minute=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
