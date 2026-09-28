"""Give the runtime role (gj_app) data access, and nothing else.

Grants cover tables that already exist AND tables created later by the migration
role, so migration order never matters. Tables that must be append-only revoke
UPDATE/DELETE in their own migration, which must depend on this one.
"""

from django.db import migrations

GRANT = """
GRANT USAGE ON SCHEMA public TO gj_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO gj_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO gj_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO gj_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO gj_app;
"""

REVOKE = """
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM gj_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE USAGE, SELECT ON SEQUENCES FROM gj_app;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM gj_app;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM gj_app;
"""


class Migration(migrations.Migration):
    dependencies = []
    operations = [migrations.RunSQL(sql=GRANT, reverse_sql=REVOKE)]
