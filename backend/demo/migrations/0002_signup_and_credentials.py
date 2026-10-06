"""Demo-only tables for party sign-up (A4, A5) and the demo passwords (A7).

No row-level security, like the other demo tables: synthetic data only, read and written only by
the demo endpoints and tooling (404 / refused unless DEMO_MODE, which runs only on localhost),
and a pending sign-up has no account yet that a policy could check.

The app role's privileges are trimmed to what each table needs:
- demo_demopendingsignup: INSERT, SELECT and DELETE (a row is deleted when the sign-up
  completes or is replaced, or once stale). Never updated.
- demo_democredential: INSERT, SELECT and UPDATE (a password change updates the row).
  Never deleted.
"""

from django.db import migrations, models

FORWARD = """
REVOKE UPDATE, TRUNCATE ON demo_demopendingsignup FROM gj_app;
REVOKE DELETE, TRUNCATE ON demo_democredential FROM gj_app;
"""

BACKWARD = """
GRANT DELETE ON demo_democredential TO gj_app;
GRANT UPDATE ON demo_demopendingsignup TO gj_app;
"""


class Migration(migrations.Migration):
    dependencies = [
        ("demo", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DemoCredential",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("user_id", models.CharField(max_length=12, unique=True)),
                ("password_encrypted", models.TextField()),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name="DemoPendingSignup",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("challenge_public_id", models.UUIDField(unique=True)),
                ("gstin_index", models.CharField(db_index=True, max_length=64)),
                ("licence_id", models.BigIntegerField()),
                ("email_encrypted", models.TextField()),
                ("business_name", models.CharField(max_length=200)),
                ("address_encrypted", models.TextField()),
                ("password_hash", models.CharField(max_length=128)),
                ("password_encrypted", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.RunSQL(sql=FORWARD, reverse_sql=BACKWARD),
    ]
