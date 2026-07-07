# Build Log — İlerleme Kaydı

Projenin hangi adımda olduğunu takip etmek için tutulan kümülatif kayıt.
Her adım: **ne yapıldı**, **neden**, ve **commit** referansı. En üstte sıradakiler.

Sıralama `docs/architecture.md`'deki veri akışını izler:
`mock-data → source-db → analytics-db (FDW) → dbt → ai-engine → api → superset → observability`

---

## 🔜 Sıradaki adımlar

- [ ] **Superset dashboard içerikleri** — `analytics` datasource'u üzerinden dataset + chart + dashboard oluşturup (UI veya `superset import-dashboards` export'u ile) `dashboard_id`'yi embed akışına bağlamak. (Altyapı — servis, embedded config, guest token — adım 10'da tamamlandı.)
- [ ] **Scheduled runner'lar** — ai-engine'de anomaly/recommendation runner sınıfları var ama container içinde timer ile tetikleyen scheduler yok (CLAUDE.md: "scheduled runners run on a timer inside the container").

---

## ✅ Tamamlananlar

### 10. Superset — servis + embedded altyapısı
**Commit:** _(henüz commit'lenmedi)_

Superset compose stack'ine eklendi; embedded dashboard + guest token altyapısı hazır.
- `superset/superset_config.py` — TODO'dan gerçek config'e: `EMBEDDED_SUPERSET` feature flag, `GUEST_ROLE_NAME=Gamma`, 300s guest token TTL, iframe embed için Talisman kapalı + CORS açık; metadata DB `superset-data` volume'ünde SQLite (analitik veri zaten analytics-db'de).
- `superset/init.sh` — idempotent bootstrap: `db upgrade` → admin kullanıcı → `superset init` → `set_database_uri` ile analytics-db'yi `analytics` datasource'u olarak kaydeder.
- `docker-compose.yml` — `superset-init` (one-shot, analytics-db healthy sonrası) + `superset` (init başarıyla bitince başlar, `apache/superset:4.1.2`) servisleri, `superset-data` volume'ü; override'a `8088:8088`.
- api tarafı zaten hazırdı (adım 7): `superset_service.py` login → guest_token akışı, RLS `user_id` scoping.
- Doğrulama: `docker compose config -q` geçerli, `bash -n init.sh` ve `py_compile superset_config.py` temiz. (Docker daemon kapalı — uçtan uca `make up` doğrulaması ilk açılışta yapılmalı.)

**Neden:** api'nin mint ettiği guest token'ın karşılığı olan Superset servisi stack'te yoktu; bu adımla embed edilebilir, RLS-scoped dashboard servis edecek altyapı tamam. Dashboard içerikleri (dataset/chart) sıradaki adımda.

### 9. Observability — metrics dilimi
**Commit:** _(henüz commit'lenmedi)_

Span'lerden türetilen RED metrikleri (rate/error/duration) Prometheus'a, oradan Grafana dashboard'una bağlandı.
- `observability/otel-collector/config.yaml` — `spanmetrics` connector eklendi; traces pipeline'ı spanmetrics'e de export ediyor, yeni `metrics` pipeline'ı (otlp + spanmetrics → `prometheus` exporter :8889).
- `observability/prometheus/prometheus.yml` — TODO'dan gerçek config'e: `otel-collector:8889` + self-scrape, 15s interval.
- `observability/grafana/provisioning/datasources/datasources.yaml` — Prometheus datasource (`uid: prometheus`).
- `observability/grafana/provisioning/dashboards/dashboards.yaml` + `observability/grafana/dashboards/service-overview.json` — auto-provision edilen "Service Overview" dashboard'u: servis bazında istek oranı, hata oranı, p95 latency (servis + endpoint).
- `docker-compose.yml` — `prometheus` servisi (`prom/prometheus:v3.2.1`) + `prometheus-data` volume; grafana artık prometheus'a da depends_on.
- Doğrulama: `docker compose config -q` geçerli, 4 YAML + dashboard JSON lint'lendi. (Collector config'in image ile runtime validate'i Docker daemon kapalı olduğundan yapılamadı — `make up` ile ilk açılışta doğrulanmalı.)

**Neden:** Trace dilimi (adım 8) span'leri Tempo'ya taşıyordu ama metrik yoktu; spanmetrics connector ile ayrı bir metrics SDK kurulumu gerekmeden her servisin RED metrikleri Grafana'da hazır dashboard olarak görünür. Observability adımı böylece tamamlandı.

### 8. Observability — trace dilimi (uçtan uca)
**Commit:** `984811b` (PR #7 → `873b003` ile main'e merge)

api/ai-engine → OTel collector → Tempo → Grafana trace akışı kuruldu.
- `observability/otel-collector/config.yaml` — OTLP receiver (gRPC 4317 / HTTP 4318) → Tempo'ya `otlp/tempo` exporter (+ debug).
- `observability/tempo/tempo.yaml` — single-binary Tempo, OTLP gRPC alır, HTTP API :3200.
- `observability/grafana/provisioning/datasources/datasources.yaml` — Tempo datasource (Explore'dan trace gezilir); anonim erişim açık.
- `docker-compose.yml` — `otel-collector`, `tempo`, `grafana` servisleri + `tempo-data`/`grafana-data` volume'leri; ai-engine ve api'nin `OTEL_EXPORTER_OTLP_ENDPOINT` default'u `http://otel-collector:4317`'e çekildi. Override'a Grafana `3000:3000`.
- **Kod**: iki serviste `core/tracing.py`'ye `instrument_app()` — FastAPI + asyncpg + httpx auto-instrumentation; `main.py`'de `create_app`'te çağrıldı; pyproject + Dockerfile'a `opentelemetry-instrumentation-{fastapi,asyncpg,httpx}` eklendi.
- Doğrulama: api 7 / ai-engine 2 test geçti, iki servis temiz import, `docker compose config` geçerli, 3 YAML config lint'lendi.

**Neden:** Her isteğin HTTP + DB + dış çağrı span'leri ve Claude çağrı metrikleri Tempo'da toplanıp Grafana'da görünür olsun. `tracing.py`'lerdeki "lands in the observability step" notu artık karşılandı. Metric/dashboard dilimi sıradaki adımda.

### 7. api servisi — public-facing katman
**Commit:** `72c11e6` (PR #4 → `6176a13` ile main'e merge)

ai-engine ile aynı `core/` pattern'i izlenerek `api/` stub'ları gerçek implementasyona çevrildi.
- `core/`: structlog JSON logging, OTel tracing, request-context middleware, typed exception hiyerarşisi (`ApiError`, `UserNotFoundError`, `AIEngineError`, `AIEngineRateLimitError`, `SupersetError`).
- **finance**: `marts.*` şemasından read-only endpoint'ler (summary, cashflow, spending, net-worth, peer-comparison), repo → service → router katmanlı.
- **chat**: `AIEngineClient` ile ai-engine'e proxy — api Claude'u **doğrudan çağırmaz** (CLAUDE.md kuralı); 429→rate-limit, 5xx→ai_engine_error eşlemesi.
- **superset**: login → guest_token akışı, her token `user_id` ile **RLS-scoped** (per-user güvenlik kuralı).
- main/config/dependencies wiring, Dockerfile, pyproject (OTel + pytest), docker-compose `api` servisi + `8001:8000` portu, `.env.example` güncellendi.
- Unit testler: finance shaping, RLS scoping, proxy hata eşlemesi — **7 passed**.

**Neden:** Kullanıcıya bakan tek giriş noktası; marts'tan veri okur, chat'i içeri proxy'ler, Superset embed için güvenli token üretir.

### 6. ai-engine — AI motoru implementasyonu
**Commit:** `354245e` (2026-06-23)

TODO-stub'lar gerçek implementasyona çevrildi: insight/anomaly/recommendation runner'lar, `ClaudeService` (güncel `output_config.format` structured output + adaptive thinking API'si, model `claude-sonnet-4-6`), context/insight repo'ları, chat & insights router'ları, Jinja2 prompt'lar, observability `core/` katmanı. Unit test (`test_insight_runner`) — 2 passed.

**Neden:** mart çıktısını okuyup Claude ile insight üretip `ai_layer`'a geri yazan iç servis.

### 5. dbt pipeline + walkthrough
**Commit:** `fbbe3cd`, `effede9` (modeller) · `5fa294e` (2026-06-11, walkthrough dokümanı)

staging → intermediate → marts (finance + ai_layer) modelleri, macro'lar, testler. `docs/dbt/pipeline-walkthrough.md` ile uçtan uca Türkçe anlatım.

**Neden:** ham veriyi BI ve AI'nin hızlı okuyacağı martlara dönüştüren dönüşüm katmanı.

### 4. analytics-db + FDW + ai insights foundation
**Commit:** `5a24864`

`postgres_fdw` kurulum SQL'i ve AI insights için foundation şeması.

### 3. CI workflow
**Commit:** `c82f6af`

GitHub Actions: dbt parse/build/test + pytest, Postgres service container ile.

### 2 & 1. İskelet + mock-data + source-db
**Commit:** `a1a00c9` (ve öncesi)

İlk DB şeması, statik referans verisi, deterministik (Faker) mock-data generator.

---

> **Not:** Bu dosya her tamamlanan adımdan sonra güncellenir. Commit'lenmemiş bir adım "henüz commit'lenmedi" olarak işaretlenir; commit'lendiğinde hash eklenir.
