"""Superset configuration — embedded dashboards with per-user guest tokens.

The api service mints guest tokens via POST /api/v1/security/guest_token/
(see api/src/services/superset_service.py); every token carries an RLS clause
(user_id = <id>) so an embedded dashboard only ever shows that user's rows.
"""

import os

SECRET_KEY = os.environ["SUPERSET_SECRET_KEY"]

# Metadata DB on the superset-data volume. SQLite is enough for this
# single-node demo stack; the analytics data itself lives in analytics-db.
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

FEATURE_FLAGS = {"EMBEDDED_SUPERSET": True}

# Guest tokens minted by the api service. The guest user acts through the
# read-only Gamma role; row access is narrowed further by the RLS clause.
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_EXP_SECONDS = 300

# Embedding: the dashboard is iframed by the app, so Talisman's frame
# protection and CSP must not block cross-origin framing.
TALISMAN_ENABLED = False
HTTP_HEADERS = {}
ENABLE_CORS = True
CORS_OPTIONS = {
    "supports_credentials": True,
    "origins": "*",
}
