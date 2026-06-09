# api — endpoint contracts, auth, guest token flow

- `/chat` — proxies user questions to ai-engine (never calls Claude directly)
- `/superset/guest-token` — per-user scoped guest token (enforced in `superset_service.py`)
- `/health` — liveness/readiness
