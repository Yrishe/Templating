from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="type",
            field=models.CharField(
                choices=[
                    ("contract_request", "Contract Request"),
                    ("contract_update", "Contract Update"),
                    ("chat_message", "Chat Message"),
                    ("manager_alert", "Manager Alert"),
                    ("system", "System"),
                ],
                max_length=50,
            ),
        ),
    ]
