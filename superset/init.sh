#!/usr/bin/env bash
# One-shot Superset bootstrap, run by the superset-init compose service:
# migrate the metadata DB, ensure the admin user, register analytics-db.
# Idempotent — safe to re-run on every `docker compose up`.
set -euo pipefail

superset db upgrade

# create-admin fails if the user already exists — fine on re-runs.
superset fab create-admin \
  --username "${SUPERSET_ADMIN_USER}" \
  --firstname Admin \
  --lastname User \
  --email admin@example.local \
  --password "${SUPERSET_ADMIN_PASSWORD}" \
  || true

superset init

# Register (or update) the analytics warehouse as a Superset database.
superset set_database_uri \
  -d analytics \
  -u "postgresql+psycopg2://${ANALYTICS_DB_USER}:${ANALYTICS_DB_PASSWORD}@analytics-db:5432/${ANALYTICS_DB_NAME}"
