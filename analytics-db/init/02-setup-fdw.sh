#!/bin/bash
# ============================================================================
# analytics-db : postgres_fdw wiring to source-db
# ----------------------------------------------------------------------------
# Runs once at DB init, after 01-schema.sql. Connection details for source-db
# come from environment variables (set on the analytics-db service in
# docker-compose.yml) — never hardcoded, so no secret lives in this file.
#
# Result: every table in source-db's `core` schema appears under `raw_core` in
# analytics-db as a foreign table. dbt staging models read source('core', ...).
#
# Ordering is safe: docker-compose makes analytics-db wait for source-db to be
# healthy, and Postgres only accepts network connections after its own init
# (schema + seed) has finished — so core.* tables exist before IMPORT runs.
# ============================================================================
set -euo pipefail

: "${SOURCE_DB_HOST:?SOURCE_DB_HOST is required}"
: "${SOURCE_DB_NAME:?SOURCE_DB_NAME is required}"
: "${SOURCE_DB_USER:?SOURCE_DB_USER is required}"
: "${SOURCE_DB_PASSWORD:?SOURCE_DB_PASSWORD is required}"
SOURCE_DB_PORT="${SOURCE_DB_PORT:-5432}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE SCHEMA IF NOT EXISTS raw_core;

DROP SERVER IF EXISTS source_srv CASCADE;
CREATE SERVER source_srv
    FOREIGN DATA WRAPPER postgres_fdw
    OPTIONS (host '${SOURCE_DB_HOST}', dbname '${SOURCE_DB_NAME}', port '${SOURCE_DB_PORT}');

CREATE USER MAPPING FOR CURRENT_USER
    SERVER source_srv
    OPTIONS (user '${SOURCE_DB_USER}', password '${SOURCE_DB_PASSWORD}');

IMPORT FOREIGN SCHEMA core
    FROM SERVER source_srv
    INTO raw_core;
SQL

echo "postgres_fdw: imported source-db core schema into raw_core"
