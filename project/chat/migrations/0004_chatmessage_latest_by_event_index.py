from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0003_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="chatmessage",
            index=models.Index(
                fields=["event", "-id"],
                name="chat_event_latest_idx",
            ),
        ),
    ]
