# api Servisi — Uçtan Uca Walkthrough

Bu doküman `api/` servisini sıfırdan, neden-öyle-yaptık mantığıyla anlatır.
Amaç: dosyaları tek tek okumadan servisin tamamını kafanda kurabilmen.

> Kardeş doküman: dbt tarafı için `docs/dbt/pipeline-walkthrough.md`.
> `api`, ai-engine ile **aynı `core/` ve katman disiplinini** paylaşır — birini
> anladıysan diğerini de anlarsın.

---

## 1. Bu servis ne işe yarar? (zihinsel model)

Mimaride iki tür FastAPI servisi var:

- **ai-engine** — *iç* servis. Claude'u çağırır, insight üretir. Dışarıya kapalı.
- **api** — *dış* servis. Kullanıcı ve Superset buraya konuşur.

`api`'nin üç görevi var:

| Görev | Endpoint | Arkada kiminle konuşur |
|---|---|---|
| Finans verisi sun | `GET /finance/users/{id}/...` | analytics-db (marts) |
| Soruyu AI'ya ilet | `POST /chat` | **ai-engine'e proxy** |
| Dashboard token üret | `POST /superset/guest-token` | Superset REST API |

**En önemli kural:** api, Claude API'sini **asla doğrudan çağırmaz**. Chat
isteklerini ai-engine'e iletir. Böylece Claude'a dair her şey (model seçimi,
token limiti, retry, prompt) tek yerde — ai-engine'de — kalır. (CLAUDE.md kuralı.)

---

## 2. Katmanlı mimari — bir istek nasıl akar?

CLAUDE.md'deki bağımlılık yönü kutsaldır:

```
routers  →  services  →  repositories / clients  →  core
```

Bir HTTP isteğinin yolculuğu:

```
İstemci ── HTTP ──►  middleware   request_id üret · süreyi ölç · hata → temiz JSON
                         │
                         ▼
                       router      SADECE HTTP işi (ince — iş mantığı yok)
                         │
                         ▼
                       service     İŞ MANTIĞI (veriyi şekillendir, kararları ver)
                         │
                         ▼
              repository / client  DB sorgusu  VEYA  dış HTTP çağrısı
                         │
                         ▼
                       core        logging · tracing · exceptions (iş mantığı BİLMEZ)
```

**Neden böyle?** Her katmanın tek bir sorumluluğu var (CLAUDE.md "one
responsibility per unit"). Router HTTP'yi bilir, service işi bilir, repo veriyi
bilir. Bir SQL değişince sadece repo'ya dokunursun; bir endpoint kontratı
değişince sadece router/şemaya. Katmanlar birbirine sızmaz.

Router'ların ne kadar ince olduğunu görmek için — `chat` endpoint'inin tamamı:

```python
@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, ai_engine: AIEngineClientDep) -> ChatResponse:
    return await ai_engine.chat(req.user_id, req.question)
```

Üç satır. Tüm zekâ `AIEngineClient`'ta.

---

## 3. Dependency Injection — parçalar nasıl birleşir?

`dependencies.py` FastAPI'nin DI sistemini kullanır. İki tür nesne var:

- **Uygulama ömrü boyunca tek olanlar** (`main.py` → `lifespan`'de bir kez kurulur,
  `app.state`'te tutulur): **DB connection pool** ve **httpx client**. Bunları her
  istekte yeniden açmak pahalı olurdu.
- **Her istekte oluşanlar** (ucuz, durumsuz sarmalayıcılar): service'ler ve
  repo'lar. Pool/http'yi alıp sararlar.

```python
def get_pool(request):  return request.app.state.pool      # tekil
def get_http(request):  return request.app.state.http      # tekil

def get_finance_service(pool: PoolDep) -> FinanceService:   # her istekte
    return FinanceService(FinanceRepository(pool))
```

Router'da bunu `Annotated` tip takma adlarıyla kullanıyoruz — `FinanceServiceDep`,
`AIEngineClientDep`, `SupersetServiceDep`. FastAPI tipe bakıp doğru nesneyi
otomatik enjekte eder. **Faydası testte:** service'ler dışarıdan bağımlılık
aldığı için testte sahte (fake) bağımlılık verip DB'siz/ağsız test yazabiliyoruz
(bkz. Bölüm 7).

---

## 4. Üç dikey, detaylı

### a) Finance — marts'tan okuma (`repo → service → router`)

**Repository** (`repositories/finance_repo.py`): `marts.*` şemasına salt-okunur
SQL. Her metot tek bir mart dilimi çeker, başka iş yapmaz:

```python
_CASHFLOW_QUERY = """
    SELECT txn_month, total_income, total_spend, net_cashflow
    FROM marts.fct_monthly_cashflow
    WHERE user_id = $1
    ORDER BY txn_month
"""
```

`get_user` bilinmeyen kullanıcıda `UserNotFoundError` fırlatır — `None`
döndürüp "hata yok gibi" davranmaz (CLAUDE.md "fail loudly, never return None
to signal failure").

**Service** (`services/finance_service.py`): ham satırları temiz şemalara
dönüştürür ve türetilmiş kararları verir. Örneğin `get_summary`, cashflow
serisinin **son elemanını** "geçen ay" olarak, net-worth serisinin son elemanını
"güncel net değer" olarak alır:

```python
last = cashflow[-1] if cashflow else None
return UserSummary(
    last_month_income = last["total_income"] if last else None,
    net_worth_latest  = net_worth[-1]["net_worth"] if net_worth else None,
    ...
)
```

**Router** (`routers/finance.py`): 5 endpoint, her biri tek satır:
`summary`, `cashflow`, `spending`, `net-worth`, `peer-comparison`.

Önemli ayrım: **DB kolon adları repo'da kalır** (`group_name`, `net_cashflow`),
dışarıya açılan şema temiz isimler kullanır (`category`, `net`). Böylece bir mart
kolonu yeniden adlandırılsa public kontrat değişmez.

### b) Chat — ai-engine'e proxy (`client → router`)

**Client** (`services/ai_engine_client.py`): httpx ile ai-engine'in `/chat`'ine
istek atar ve **hataları anlamlı tiplere çevirir**:

```python
except httpx.HTTPStatusError as exc:
    if exc.response.status_code == 429:
        raise AIEngineRateLimitError(...)      # → kullanıcıya 429
    raise AIEngineError(...)                   # → 502
except httpx.HTTPError as exc:
    raise AIEngineError("ai-engine unreachable: ...")   # ağ hatası → 502
```

Böylece Claude'un rate-limit'i, ai-engine üzerinden geçip kullanıcıya **temiz bir
429** olarak yansır; ağ kopması da 502 olur. Router yine tek satır.

### c) Superset — kullanıcı-bazlı guest token (`service → router`)

**Service** (`services/superset_service.py`): iki adımlı akış —

1. Admin olarak Superset'e `POST /api/v1/security/login` → `access_token` al.
2. O token'la `POST /api/v1/security/guest_token/` → guest token üret.

**En kritik satır** güvenlikle ilgili:

```python
"rls": [{"clause": f"user_id = {int(user_id)}"}]
```

Bu **Row-Level Security** kuralı: üretilen token ile açılan dashboard, SQL'in
sonuna `user_id = 42` filtresini ekler. Yani 42 numaralı kullanıcı **fiziksel
olarak** sadece kendi verisini görebilir — başkasının satırına erişemez. CLAUDE.md:
"Guest tokens are scoped per user — superset_service.py enforces this."

(`int(user_id)` ile sayıya zorluyoruz — clause string'ine güvenilmeyen değer
girmesin diye.)

---

## 5. `core/` — ortak altyapı (ai-engine ile birebir aynı)

CLAUDE.md "every service has the same `core/` layer" der. api'de de:

- **`logging.py`** — structlog ile **JSON** log. `request_id` middleware tarafından
  bağlanır, her log satırında görünür.
- **`tracing.py`** — OpenTelemetry. `OTEL_EXPORTER_OTLP_ENDPOINT` boşsa span'ler
  üretilir ama gönderilmez (uygulama her yerde çalışır); endpoint set edilince
  collector'a akar. **Sıradaki observability adımı bunu kullanacak.**
- **`middleware.py`** — her isteğe `request_id`, süre ölçümü, ve domain
  hatalarını HTTP koduna çeviren handler'lar:

  | Exception | HTTP |
  |---|---|
  | `UserNotFoundError` | 404 |
  | `AIEngineRateLimitError` | 429 |
  | `AIEngineError` / `SupersetError` | 502 |
  | `ApiError` (taban) | 500 |

- **`exceptions.py`** — tipli hata hiyerarşisi. Taban `ApiError`, hepsi ondan türer.
  Bare `Exception` yok (CLAUDE.md).

---

## 6. Config ve ortam değişkenleri

`config.py` pydantic-settings ile **her ayarı env'den** okur (CLAUDE.md "secrets
from env only"):

- `AI_ENGINE_URL` — proxy hedefi
- `SUPERSET_URL`, `SUPERSET_ADMIN_USER`, `SUPERSET_ADMIN_PASSWORD`
- `ANALYTICS_DB_*` — `analytics_dsn` property'sine birleşir
- `SERVICE_NAME`, `LOG_LEVEL`, `OTEL_EXPORTER_OTLP_ENDPOINT`

Yeni env eklenince `.env.example` güncellenir (CLAUDE.md kuralı — bu adımda
`SUPERSET_ADMIN_*` eklendi).

---

## 7. Test stratejisi — DB'siz, ağsız, hızlı

3 unit test var, hepsi **gerçek I/O olmadan** çalışır (CI'da Postgres/ağ
gerektirmez):

- `test_finance_service.py` — **sahte repo** (`FakeRepo`) verir, service'in
  satırları doğru şekillendirdiğini ve bilinmeyen kullanıcıda `UserNotFoundError`
  fırlattığını doğrular. DI sayesinde mümkün.
- `test_superset_service.py` — **`httpx.MockTransport`** ile Superset'i taklit
  eder; **RLS clause'unun `user_id = 42` içerdiğini** asserter (güvenlik-kritik
  davranışın testi).
- `test_ai_engine_client.py` — yine MockTransport; ai-engine'in 429'unun
  `AIEngineRateLimitError`'a, 5xx'in `AIEngineError`'a çevrildiğini doğrular.

Çalıştırma: `cd api && uv run pytest -q` → **7 passed**.

---

## 8. Çalıştırma

`docker-compose.yml`'de `api` servisi tanımlı; `analytics-db` sağlıklı olunca
ayağa kalkar. Yerel geliştirmede `docker-compose.override.yml` host portunu açar:

```
api  →  http://localhost:8001   (konteyner içinde 8000)
ai-engine  →  http://localhost:8000
```

Kayıtlı route'lar: `/health`, `/health/ready`, `/chat`,
`/finance/users/{id}/{summary,cashflow,spending,net-worth,peer-comparison}`,
`/superset/guest-token`.

---

## 9. Tek cümlelik özet

> **api = ince router'lar + akıllı service'ler.** Marts'tan salt-okunur veri
> sunar, chat'i ai-engine'e proxy'ler (Claude'a hiç dokunmadan), ve Superset
> token'larını kullanıcı başına RLS ile kısıtlar — hepsi ai-engine ile aynı
> `core/` ve katman disiplininde.
