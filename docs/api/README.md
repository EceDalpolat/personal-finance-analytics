# api — endpoint contracts, auth, guest token flow

Uçtan uca anlatım (Türkçe): **[walkthrough.md](walkthrough.md)** — servisin
zihinsel modeli, katmanlı mimari, üç dikey (finance / chat proxy / superset),
test stratejisi.

## Endpoint kontratları

- `/chat` — proxies user questions to ai-engine (never calls Claude directly)
- `/finance/users/{id}/{summary,cashflow,spending,net-worth,peer-comparison}` — read-only mart data
- `/superset/guest-token` — per-user scoped guest token, RLS-filtered (enforced in `superset_service.py`)
- `/health`, `/health/ready` — liveness/readiness
