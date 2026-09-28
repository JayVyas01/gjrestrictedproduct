#!/usr/bin/env bash
# Creates the two database roles the application uses:
#   gj_owner - owns the schema, runs migrations and tests (never used by the running app)
#   gj_app   - the running application: no ownership, no DDL, cannot bypass row-level security
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" \
  -v owner_pw="$GJ_OWNER_PASSWORD" -v app_pw="$GJ_APP_PASSWORD" <<'SQL'
CREATE ROLE gj_owner LOGIN CREATEDB NOSUPERUSER NOCREATEROLE PASSWORD :'owner_pw';
CREATE ROLE gj_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD :'app_pw';
-- Lets tests run "SET ROLE gj_app" to exercise production privileges.
GRANT gj_app TO gj_owner;
CREATE DATABASE gjrp OWNER gj_owner;
REVOKE ALL ON DATABASE gjrp FROM PUBLIC;
GRANT CONNECT ON DATABASE gjrp TO gj_app;
SQL
