from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="file",
            field=models.FileField(blank=True, null=True, upload_to="contracts/"),
        ),
        migrations.AlterField(
            model_name="contract",
            name="content",
            field=models.TextField(blank=True),
        ),
    ]
