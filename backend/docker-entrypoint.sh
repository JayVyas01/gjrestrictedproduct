#!/bin/sh
# Backend container start-up (demo stack). Never seeds: that is `make demo-seed`.
#   1. wait for the database
#   2. migrate (and create the cache table) as the schema owner, gj_owner
#   3. create due oversight batches (idempotent; the command acts as SYSTEM)
#   4. serve the app with gunicorn as gj_app, which cannot change the schema or bypass RLS
set -eu

as_owner() {
    DB_USER="$DB_OWNER_USER" DB_PASSWORD="$DB_OWNER_PASSWORD" "$@"
}

echo "Waiting for the database..."
python - <<'PY'
import os, sys, time
import psycopg

for _ in range(60):
    try:
        psycopg.connect(
            host=os.environ["DB_HOST"], port=os.environ.get("DB_PORT", "5432"),
            dbname=os.environ["DB_NAME"], user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"], connect_timeout=2,
        ).close()
        sys.exit(0)
    except psycopg.OperationalError:
        time.sleep(1)
sys.exit("The database did not become reachable.")
PY

as_owner python manage.py migrate --noinput
as_owner python manage.py createcachetable
python manage.py create_due_batches

# The app process never holds the owner's password.
unset DB_OWNER_USER DB_OWNER_PASSWORD
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -
