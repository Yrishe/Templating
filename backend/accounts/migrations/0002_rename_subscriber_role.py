from __future__ import annotations

from django.db import migrations, models


def rename_subscriber_to_account(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="subscriber").update(role="account")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        # 1. Update the field choices and default
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("manager", "Manager"),
                    ("account", "Account"),
                    ("invited_account", "Invited Account"),
                ],
                default="account",
                max_length=20,
            ),
        ),
        # 2. Migrate existing "subscriber" rows to "account"
        migrations.RunPython(rename_subscriber_to_account, migrations.RunPython.noop),
    ]
