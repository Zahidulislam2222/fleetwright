#!/bin/sh
# Creates Fleetwright's database roles and the two databases on first start.
# Passwords arrive through the container environment; psql variables keep them out of the SQL text.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v owner_pw="$FWDEV_PG_OWNER_PASSWORD" -v app_pw="$FWDEV_PG_APP_PASSWORD" \
  -v worker_pw="$FWDEV_PG_WORKER_PASSWORD" -v board_pw="$FWDEV_PG_BOARD_PASSWORD" <<'SQL'
CREATE ROLE fw_owner LOGIN PASSWORD :'owner_pw';
CREATE ROLE fw_app LOGIN PASSWORD :'app_pw';
CREATE ROLE fw_worker LOGIN PASSWORD :'worker_pw';
CREATE ROLE fw_board LOGIN PASSWORD :'board_pw';
CREATE DATABASE fleetwright OWNER fw_owner;
CREATE DATABASE mockboard OWNER fw_board;
REVOKE ALL ON DATABASE fleetwright FROM PUBLIC;
REVOKE ALL ON DATABASE mockboard FROM PUBLIC;
GRANT CONNECT ON DATABASE fleetwright TO fw_app, fw_worker;
SQL
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname fleetwright <<'SQL'
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO fw_app, fw_worker;
ALTER SCHEMA public OWNER TO fw_owner;
SQL
