#!/usr/bin/env bash
# Create the StandupPilot role and the development and test databases.
# Runs as the postgres superuser; invoked by scripts/setup.sh. Idempotent.
#
# Expects: APP_USER, APP_PASSWORD, APP_DB, TEST_DB in the environment.
set -euo pipefail

: "${APP_USER:?APP_USER required}"
: "${APP_PASSWORD:?APP_PASSWORD required}"
: "${APP_DB:?APP_DB required}"
: "${TEST_DB:?TEST_DB required}"

PSQL=(psql -Xq -v ON_ERROR_STOP=1)

# Role. Identifier and password are passed as psql variables, never string-interpolated.
if [[ "$(psql -XtAc "select 1 from pg_roles where rolname = \$\$${APP_USER}\$\$")" == "1" ]]; then
  "${PSQL[@]}" -v user="$APP_USER" -v pw="$APP_PASSWORD" <<'SQL'
alter role :"user" with login password :'pw';
SQL
  echo "role $APP_USER already existed - password refreshed from .env"
else
  "${PSQL[@]}" -v user="$APP_USER" -v pw="$APP_PASSWORD" <<'SQL'
create role :"user" with login password :'pw';
SQL
  echo "created role $APP_USER"
fi

# Databases owned by the application role so migrations can create objects.
for db in "$APP_DB" "$TEST_DB"; do
  if [[ "$(psql -XtAc "select 1 from pg_database where datname = \$\$${db}\$\$")" == "1" ]]; then
    echo "database $db already exists"
  else
    "${PSQL[@]}" -v db="$db" -v owner="$APP_USER" <<'SQL'
create database :"db" owner :"owner" encoding 'UTF8';
SQL
    echo "created database $db"
  fi
  "${PSQL[@]}" -d "$db" -v owner="$APP_USER" <<'SQL'
grant all on schema public to :"owner";
SQL
done

echo "PostgreSQL bootstrap complete"
