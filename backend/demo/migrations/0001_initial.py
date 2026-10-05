"""Demo-only tables: the demo SMS inbox and the persona list.

No row-level security, on purpose: both tables hold only synthetic demo data, are read only by
the anonymous demo endpoints (which answer 404 unless DEMO_MODE, and DEMO_MODE refuses to run
anywhere but localhost), and have no owner a policy could check: inbox codes are needed before
anyone has signed in. The inbox never stores a full contact, only its last 4 digits.

The app role may only INSERT and SELECT. Nothing updates or deletes a demo row: a demo reset
recreates the whole database (`make demo-reset`).
"""

from django.db import migrations, models

FORWARD = """
REVOKE UPDATE, DELETE, TRUNCATE ON demo_demoinboxmessage FROM gj_app;
REVOKE UPDATE, DELETE, TRUNCATE ON demo_demopersona FROM gj_app;
"""

BACKWARD = """
GRANT UPDATE, DELETE ON demo_demopersona TO gj_app;
GRANT UPDATE, DELETE ON demo_demoinboxmessage TO gj_app;
"""


class Migration(migrations.Migration):
    initial = True

    dependencies = [("core", "0001_app_role_privileges")]

    operations = [
        migrations.CreateModel(
            name="DemoPersona",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("key", models.CharField(max_length=40, unique=True)),
                ("user_id", models.CharField(max_length=12)),
            ],
        ),
        migrations.CreateModel(
            name="DemoInboxMessage",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("user_id", models.CharField(blank=True, max_length=12)),
                ("display_name", models.CharField(max_length=200)),
                ("contact_last4", models.CharField(max_length=4)),
                ("code", models.CharField(max_length=6)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "indexes": [models.Index(fields=["-created_at", "-id"], name="demo_inbox_newest")],
            },
        ),
        migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD),
    ]
