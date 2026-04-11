from __future__ import annotations

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0003_notification_read_by"),
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="caused_notifications",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="notification",
            name="triggered_by_timeline_event",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="notifications",
                to="projects.timelineevent",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("contract_request", "Contract Request"),
                    ("contract_request_approved", "Contract Request Approved"),
                    ("contract_request_rejected", "Contract Request Rejected"),
                    ("contract_update", "Contract Update"),
                    ("chat_message", "Chat Message"),
                    ("new_email", "New Email"),
                    ("deadline_upcoming", "Deadline Upcoming"),
                    ("manager_alert", "Manager Alert"),
                    ("system", "System"),
                ],
                max_length=50,
            ),
        ),
    ]
