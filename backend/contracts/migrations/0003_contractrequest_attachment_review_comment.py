from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contracts", "0002_contract_pdf_file"),
    ]

    operations = [
        migrations.AddField(
            model_name="contractrequest",
            name="attachment",
            field=models.FileField(
                blank=True, null=True, upload_to="contract_requests/"
            ),
        ),
        migrations.AddField(
            model_name="contractrequest",
            name="review_comment",
            field=models.TextField(blank=True),
        ),
    ]
