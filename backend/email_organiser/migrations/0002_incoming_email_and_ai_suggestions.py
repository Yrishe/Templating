import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("email_organiser", "0001_initial"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="IncomingEmail",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("sender_email", models.EmailField(max_length=254)),
                ("sender_name", models.CharField(blank=True, max_length=255)),
                ("subject", models.CharField(blank=True, max_length=998)),
                ("body_plain", models.TextField(blank=True)),
                ("body_html", models.TextField(blank=True)),
                ("message_id", models.CharField(max_length=998, unique=True)),
                ("received_at", models.DateTimeField()),
                ("raw_payload", models.JSONField(blank=True, null=True)),
                ("is_processed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="incoming_emails",
                        to="projects.project",
                    ),
                ),
            ],
            options={
                "ordering": ["-received_at"],
                "indexes": [
                    models.Index(fields=["project"], name="email_organ_project_idx"),
                    models.Index(fields=["received_at"], name="email_organ_recv_idx"),
                ],
            },
        ),
        migrations.AddField(
            model_name="finalresponse",
            name="source_incoming_email",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="suggested_replies",
                to="email_organiser.incomingemail",
            ),
        ),
        migrations.AddField(
            model_name="finalresponse",
            name="is_ai_generated",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="finalresponse",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("suggested", "AI Suggested"),
                    ("sent", "Sent"),
                ],
                default="draft",
                max_length=10,
            ),
        ),
    ]
