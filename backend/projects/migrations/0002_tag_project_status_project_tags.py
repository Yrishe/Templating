import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Tag",
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
                ("name", models.CharField(max_length=64, unique=True)),
                ("color", models.CharField(default="#6B7280", max_length=7)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_tags",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
            },
        ),
        migrations.AddField(
            model_name="project",
            name="status",
            field=models.CharField(
                choices=[
                    ("active", "Active"),
                    ("completed", "Completed"),
                    ("archived", "Archived"),
                ],
                default="active",
                max_length=20,
            ),
        ),
        migrations.AddIndex(
            model_name="project",
            index=models.Index(fields=["status"], name="projects_pr_status_idx"),
        ),
        migrations.AddField(
            model_name="project",
            name="tags",
            field=models.ManyToManyField(
                blank=True, related_name="projects", to="projects.tag"
            ),
        ),
    ]
