# Build Log — İlerleme Kaydı

Projenin hangi adımda olduğunu takip etmek için tutulan kümülatif kayıt.
Her adım: **ne yapıldı**, **neden**, ve **commit** referansı. En üstte sıradakiler.

Sıralama `docs/architecture.md`'deki veri akışını izler:
`mock-data → source-db → analytics-db (FDW) → dbt → ai-engine → api → superset → observability`

---

## 🔜 Sıradaki adımlar

- [ ] **Observability collector wiring** — `observability/` (OTel collector + Prometheus + Tempo + Grafana). `OTEL_EXPORTER_OTLP_ENDPOINT` set edilince ai-engine ve api trace'leri aksın. İki servisin `core/tracing.py`'sindeki "lands in the observability step" notu bunu bekliyor.
- [ ] **Superset dashboard config** — `superset/` (datasource bağlantısı, embedded dashboard, api'nin guest-token'ı ile embed entegrasyonu).
- [ ] **Scheduled runner'lar** — ai-engine'de anomaly/recommendation runner sınıfları var ama container içinde timer ile tetikleyen scheduler yok (CLAUDE.md: "scheduled runners run on a timer inside the container").

---

## ✅ Tamamlananlar

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
