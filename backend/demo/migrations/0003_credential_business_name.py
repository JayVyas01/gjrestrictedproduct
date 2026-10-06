"""The business name a party gives at sign-up, kept for parties.csv (blank for seeded ones)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("demo", "0002_signup_and_credentials"),
    ]

    operations = [
        migrations.AddField(
            model_name="democredential",
            name="business_name",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
