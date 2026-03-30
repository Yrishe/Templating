from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("management")

# Use Django settings with the CELERY_ namespace
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all INSTALLED_APPS
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
