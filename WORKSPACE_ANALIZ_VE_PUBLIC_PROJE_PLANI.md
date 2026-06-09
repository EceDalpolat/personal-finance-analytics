# Workspace Analizi & Public dbt Projesi Planı

> Amaç: Bu workspace'i tam anlamak + aynı mimarinin **mock veriyle çalışan, public/portfolyo'ya uygun** bir kopyasını kurup dbt pipeline'ını uçtan uca öğrendiğini göstermek.

---

## BÖLÜM 1 — Bu workspace tam olarak ne?

Burası **Grid Analytics** adlı bir İK/yetenek analitiği platformunun **lokal geliştirme ortamı** (`ga-workspace`). Tek `docker compose up` ile tüm stack ayağa kalkıyor. Üç ana repo'yu git submodule olarak topluyor:

| Modül | Repo | Görevi |
|-------|------|--------|
| `modules/dbt` | ga-dbt | **dbt projesi — 103 model.** İşin kalbi. |
| `modules/superset` | ga-superset | Apache Superset (dashboard/BI) + K8s manifestleri |
| `modules/analytics-api` | ga-analytics-api | Guest-token API (FastAPI) — Superset'i app'e gömmek için |

**İş alanı (domain):** Çalışanlara uygulanan psikometrik testlerin (OCEAN/Big5, Saville Wave, AON bilişsel, Assessment Center, 360° performans) ham puanlarını alıp; yetkinlik, EQ, satış potansiyeli, liderlik etkisi, risk profili gibi **iş-hazır analitik tablolara** dönüştürmek. Çıktı Superset dashboard'larında sunuluyor.

### Stack'in bileşenleri (docker-compose.yml)

```
                        ┌──────────────┐
                        │   Superset   │ :8088   (dashboard / SQL Lab)
                        │  + worker    │
                        │  + beat      │
                        └──────┬───────┘
                superset-db (PG16) · superset-redis
                               │
                               │ sorgular
                               ▼
        ┌──────────────────────────────────────────────┐
        │            analytics-db  (PG16) :5434          │  ← dbt buraya YAZAR
        │   şemalar: staging_* , intermediate , marts_*  │
        │                                                │
        │   postgres_fdw ile 3 kaynağa "foreign" bağlı:  │
        │     raw_core / raw_org  ← mock-grid-core :5433  │
        │     raw_hire            ← mock-grid-hire :5436  │
        │     raw_perform         ← mock-grid-perform:5437│
        └──────────────────────────────────────────────┘
                  ▲              ▲              ▲
            mock-grid-core  mock-grid-hire  mock-grid-perform
            (her biri PG16, cluster pg_dump'tan restore edilir)
```

**Kritik mimari fikir — FDW (Foreign Data Wrapper):**
Kaynak veritabanları (core, hire, perform) ayrı Postgres container'ları. `analytics-db` bunlara `postgres_fdw` ile bağlanıp tablolarını `raw_core`, `raw_org`, `raw_hire`, `raw_perform` şemaları altında **sanki kendi tablolarıymış gibi** görüyor ([02-setup-fdw.sql](mock-sources/init/02-setup-fdw.sql)). Böylece dbt tek bir veritabanına bağlanıp birden fazla kaynaktan okuyabiliyor. Bu, prod/UAT cluster'ındaki mikroservis-başına-DB düzenini birebir taklit ediyor.

**Kaynak veri nasıl geliyor:** Cluster'dan alınan `core.dump`, `hire.dump`, `perform.dump` (custom-format `pg_dump`) dosyaları `DUMPS_DIR`'e konuyor; container ilk açılışta [restore.sh](mock-sources/restore.sh) ile bunları geri yüklüyor. **Yani şu an "mock" dediği şey gerçekte cluster verisinin sanitize edilmiş dump'ı — senin yapacağın public projede burayı tamamen sentetik mock veriyle değiştireceğiz.**

**Çoklu ortam:** `envs/dev.env` ve `envs/uat.env` + `COMPOSE_PROJECT_NAME` sayesinde dev ve uat stack'leri yan yana çalışabiliyor. `data-sync/` altında snapshot'lar (`pg_dump .sql.gz`) ve bir Makefile var.

---

## BÖLÜM 2 — dbt projesi (asıl öğrenmen gereken kısım)

Konum: [modules/dbt](modules/dbt). dbt Core **1.11**, adapter **postgres**, paket yöneticisi **uv**.

### 2.1 Klasör yapısı ve katman felsefesi

dbt'nin standart **3 katmanlı (medallion-benzeri) mimarisi**:

```
models/
├── sources/          # 5 YAML: core, org, hire, perform, canonical  → ham FDW tabloları tanımlanır
├── staging/          # Kaynakla 1:1, sadece rename + cast. Materialization: VIEW
│   ├── core/         #   stg_core__surveys, stg_core__survey_scores, ...
│   ├── org/          #   stg_org__users, stg_org__positions, ...
│   ├── perform/
│   └── canonical/    #   seed CSV'lerden gelen referans veri
├── intermediate/     # İş mantığı: join/union/filtre. Materialization: EPHEMERAL (CTE gibi gömülür)
│   ├── core/         #   int_behavioral_scores, int_cognitive_scores, int_assessment_scores_*
│   ├── org/          #   int_org__hierarchy_closure (org ağacı!), int_org__employees_current
│   ├── profile/      #   int_profile_area_risk_scores, ...
│   └── perform/
└── marts/            # İş-hazır son tablolar. Materialization: TABLE
    ├── v1.0/         #   dashboard'a 1:1 bakan martlar (versiyonlanmış, schema: marts_v1_0)
    │   ├── employees/          dim_employee, fct_employee_summary, fct_employee_360_scores
    │   ├── company_overview/   mart_company_overview_big5_spider, ...
    │   ├── eq_potential/       fct_dashboard_eq_potential, ...
    │   ├── sales_potential/    ...
    │   ├── liderlik_etki/      ...
    │   ├── uzmanlik_etki/      ...
    │   ├── ac_potential/       ...
    │   ├── ai_layer/           mart_ai_* (9box, swot, role-fit, risk türevleri)
    │   └── main_dashboard/     mart_main_potential_summary (590 satır — en büyük model)
    └── security/     # access_map_employee — Row-Level Security (kim hangi çalışanı görür)
```

**Katman kuralları (`dbt_project.yml`'de tanımlı):**
- `staging` → `view` (hafif, disk yemez)
- `intermediate` → `ephemeral` (fiziksel tablo değil, alt sorgulara CTE olarak gömülür)
- `marts` → `table` (BI hızlı okusun diye materialize edilir)
- `seeds` → `public` şemasına yüklenir
- `deprecated/` → `+enabled: false` (çalışmaz, arşiv)

### 2.2 Bu projeyi "normal bir dbt tutorial"dan ayıran ileri özellikler

Bunları öğrendiğini gösterirsen seviye atlarsın:

1. **`sources` + freshness:** [core.yml](modules/dbt/models/sources/core.yml) gibi dosyalarda her tablo, kolon, açıklama, ve **testler** (unique, not_null, relationships, accepted_values) tanımlı. `loaded_at_field` + `freshness` ile veri tazeliği denetimi.
2. **seeds (referans veri):** [seeds/canonical/](modules/dbt/seeds/canonical) — 30+ CSV. Boyut tanımları, framework eşlemeleri (OCEAN→Saville), 9box matrisi, skor bantları. ~2100 satır. "Git'te versiyonlanan iş kuralları."
3. **macros (Jinja ile DRY SQL):** [scoring_formulas.sql](modules/dbt/macros/scoring_formulas.sql) — `ga_calc_presence`, `ga_calc_underuse`, `ga_calc_overdrive` gibi yeniden kullanılan skorlama formülleri. Ayrıca `apply_native_rls`, `add_supervisor_id` gibi RLS/güvenlik macroları.
4. **Singular + generic testler:** [tests/](modules/dbt/tests) — `assert_*_is_unique.sql` (grain testleri), `test_score_range`, `test_selection_equals_benchmark` gibi özel testler.
5. **exposures:** [superset_dashboards.yml](modules/dbt/models/exposures/superset_dashboards.yml) — dbt modellerinin hangi dashboard tarafından tüketildiğini belgeler (lineage'ı BI'a kadar uzatır).
6. **semantic models:** `models/semantic_models/` — dbt Semantic Layer / MetricFlow tanımları.
7. **versiyonlu martlar:** `marts/v1.0/` + `+schema: marts_v1_0` — dashboard sözleşmelerini kırmadan evrim.
8. **Row-Level Security:** `marts/security/access_map_employee.sql` + RLS macroları — bir yöneticinin sadece kendi ekibini görmesini sağlayan erişim haritası.
9. **packages:** `dbt_utils`, `codegen`, `dbt_expectations` ([packages.yml](modules/dbt/packages.yml)).

### 2.3 Tipik veri akışı (bir örnek zincir)

```
raw_core.participant_survey_dimension_score   (FDW kaynağı — ham puan)
        │  source('core', ...)
        ▼
stg_core__survey_scores                         (sadece rename/cast — VIEW)
        │  ref()
        ▼
int_assessment_scores_raw → _enriched          (join: survey, dimension, user — EPHEMERAL)
        │
        ▼
int_behavioral_scores                           (OCEAN→Saville dönüşümü + "son değerlendirme" dedup — TABLE)
        │  + canonical_dimension_mapping (seed) ile join
        ▼
fct_employee_behavioral_latest / fct_employee_summary   (mart — TABLE)
        │
        ▼
mart_company_overview_big5_spider, mart_main_potential_summary, ...  (dashboard martları)
        │  exposure
        ▼
Superset dashboard
```

[int_behavioral_scores.sql](modules/dbt/models/intermediate/core/int_behavioral_scores.sql) bu zincirin en öğretici parçası: framework filtresi → seed ile mapping join → DIRECT/AGGREGATE/NULL mapping tipleri → çalışan×boyut bazında son test'e dedup.

### 2.4 Çalıştırma & orkestrasyon

```bash
# Lokal (compose)
docker compose run --rm dbt build              # seed → run → test (hepsi)
docker compose run --rm dbt run --select state:modified+   # sadece değişenler
```

- **Dockerfile** ([modules/dbt/Dockerfile](modules/dbt/Dockerfile)): `uv` ile bağımlılık → `dbt deps` → `dbt parse` (build sırasında syntax doğrulama) → non-root user. Profesyonel bir CI-dostu image.
- **Prod orkestrasyon:** K8s üzerinde **Argo Workflows** ([workflowtemplate.yaml](modules/dbt/k8s/base/workflowtemplate.yaml)) — `seed → run → test` DAG'ı; CronWorkflow ile zamanlanmış. CI: GitLab CI component'leri ile image build + deploy.
- **profiles.yml:** dev (localhost:5434) + prod (env_var'lardan). `target: dev`.

---

## BÖLÜM 3 — Public/portfolyo projesi planı

Hedef: Aynı mimariyi **gerçek müşteri verisi olmadan, %100 sentetik mock veriyle**, GitHub'da paylaşılabilir bir repo olarak yeniden kurmak. dbt'nin tüm yeteneklerini (sources, staging/int/marts, seeds, macros, tests, snapshots, exposures, docs) sergileyecek.

### 3.1 İki seçenek: ne kadar sadeleştirelim?

| | **A) Sadık kopya** | **B) Sadeleştirilmiş portfolyo** *(önerilen)* |
|---|---|---|
| Kaynak DB sayısı | 3 (core/hire/perform) + FDW | 1 Postgres, 3 şema (FDW şart değil) |
| Model sayısı | ~100 | ~20-30 (her katmandan örnek) |
| Superset | Tam stack | Opsiyonel (sona bırak) / metabase |
| Domain | Aynı İK/psikometri | Aynı domain, mock org (zaten `mock_org_v1.md` hazır!) |
| Kurulması | Günler | 2-4 gün |

**Öneri: B.** dbt becerisini göstermek için 100 model gerekmez; **her dbt özelliğinden temsilci içeren temiz bir proje** daha etkileyici. FDW'yi tek DB'de 3 şema ile taklit edip kavramı yine gösterebilirsin (istersen FDW'yi de ekleyip "bonus" yaparsın).

### 3.2 Önerilen public mimari

```
mock-hr-analytics/                  (yeni public repo)
├── docker-compose.yml              # source-db (PG) + analytics-db (PG) [+ superset opsiyonel]
├── mock-data/
│   ├── generate.py                 # sentetik veri üreteci (Faker + senin psikometri kuralların)
│   └── seed_sources.sql            # üretilen veriyi kaynak şemalara basar
├── dbt/
│   ├── models/{staging,intermediate,marts}/
│   ├── seeds/                      # canonical referans CSV'leri (mock_org_v1.md'den türet)
│   ├── macros/                     # scoring_formulas vb.
│   ├── tests/
│   ├── snapshots/                  # SCD2 örneği (örn. çalışan pozisyon değişimi)
│   ├── models/exposures/
│   ├── dbt_project.yml · profiles.yml · packages.yml
└── README.md  (mimari diyagramı + "bu projede gösterdiğim dbt yetenekleri" listesi)
```

### 3.3 Mock veri stratejisi (en kritik kısım)

Elinde zaten **muazzam bir başlangıç** var — `mock_org_v1.md` 5 sektör için tam org hiyerarşisi + rol-bazlı OCEAN/Saville profilleri ve **tutarlılık kuralları** içeriyor (örn. `Processing Details = Conscientiousness ± 1`). Bunu veri üretecine çevireceğiz.

**Üretim katmanları:**
1. **Org yapısı:** `users`, `position`, `leadership_level`, `position_group` — `mock_org_v1.md`'deki hiyerarşiden. Faker ile isim/email; `supervisor_user_id` ile raporlama ağacı.
2. **Test tanımları (statik):** `survey`, `survey_category`, `dimension`, `survey_dimension` — Saville 36 boyut, OCEAN 30 faset, AON. Bunlar seed/sabit.
3. **Test sonuçları (üretilen):** `project_participant`, `survey_participant`, `participant_survey_dimension_score` — her çalışana, rolüne uygun profil dağılımından **örneklenen** puanlar (gerçekçi olması için role göre merkezli + gürültü, ve `mock_org_v1.md`'deki çapraz-tutarlılık kuralları uygulanır).
4. **Performans:** `performance`, `performance_participant` — 360°/yıllık skorlar.

> İpucu: Üreteci **deterministik** yap (sabit seed) ki `docker compose up` her seferinde aynı veriyi versin — public demoda tekrar üretilebilirlik önemli.

### 3.4 Adım adım yol haritası

1. **İskelet:** Yeni repo + `docker-compose.yml` (1 source PG + 1 analytics PG). `dbt init` ile boş proje.
2. **Kaynak şema + mock üreteç:** `mock-data/generate.py` yaz; `source-db`'ye `core`/`org`/`perform` şemaları + tabloları + sentetik satırları bas. (`mock_org_v1.md`'yi referans al.)
3. **FDW (opsiyonel ama etkileyici):** analytics-db'den source-db'ye `postgres_fdw` ile `raw_*` şemaları — buradaki [02-setup-fdw.sql](mock-sources/init/02-setup-fdw.sql)'i sadeleştirerek kopyala. (Sadeleştirme istersen: dbt'yi doğrudan source-db'ye bağla, FDW'yi atla.)
4. **sources + staging:** `models/sources/*.yml` (test'lerle) → her tablo için `stg_*` (rename/cast, view).
5. **seeds:** canonical referans CSV'leri ekle (boyutlar, OCEAN→Saville mapping, skor bantları).
6. **intermediate:** en az 2-3 anlamlı dönüşüm — örn. `int_behavioral_scores` (mapping + dedup), `int_org__hierarchy_closure` (recursive CTE ile org ağacı).
7. **marts:** `dim_employee`, `fct_employee_summary`, ve 2-3 dashboard martı (örn. big5_spider, potential_summary).
8. **macros + tests:** scoring macroları + grain/uniqueness testleri + bir generic test (`test_score_range`).
9. **snapshots:** bir SCD2 örneği (çalışanın pozisyon değişimini izleyen).
10. **exposures + docs:** exposure YAML + `dbt docs generate` (lineage grafiği — portfolyoda harika görünür).
11. **(Opsiyonel) Superset/Metabase:** martlara bağlı 1-2 dashboard, ekran görüntüsü README'ye.
12. **CI:** GitHub Actions — `dbt deps && dbt parse` + (servisli) `dbt build && dbt test`. Burada bir GitHub Actions örneği koy (Postgres service container ile).
13. **README:** mimari diyagram + "Gösterilen dbt yetenekleri" checklist'i.

### 3.5 README'de vurgulanacak "dbt yetkinlik" listesi

- [ ] Çok-katmanlı mimari (staging→intermediate→marts), katman-bazlı materialization
- [ ] `sources` + freshness + kolon-seviye testler
- [ ] `seeds` ile versiyonlu referans veri
- [ ] Jinja `macros` ile DRY skorlama formülleri
- [ ] Generic + singular `tests` (grain/uniqueness/accepted_values/relationships)
- [ ] `snapshots` (SCD2)
- [ ] `exposures` (BI'a kadar lineage) + `dbt docs`
- [ ] `ref`/`source` ile bağımlılık grafiği, `state:modified+` ile seçici çalıştırma
- [ ] Docker + CI (GitHub Actions) ile reprodüklenebilir pipeline
- [ ] (Bonus) postgres_fdw ile çok-kaynaklı mimari, RLS, versiyonlu martlar

---

## BÖLÜM 4 — Dikkat / temizlik notları

- **Gizlilik:** Public'e taşırken `gitlab.qkare.com` URL'leri, gerçek tenant_id'ler (örn. tenant 6/8), e-postalar, `data-sync/` içindeki gerçek `pg_dump` snapshot'ları **gitmemeli**. Tamamı sentetik olmalı. (Workspace zaten "sanitize client references" commit'i görmüş ama dikkat.)
- **Kök dizindeki `.md` raporları** (`IK_*`, `IP_RISK_*`, `IS_MANTIGI_RAPORU.md`, `kisillik-env 1.md`, `mock_org_v1.md`) senin domain/psikometri çalışman — public projede mock veri kurallarının **kaynağı** olarak çok değerli, ama içlerinde gerçek müşteri referansı var mı diye taranmalı.
- `mock-org/scripts/` boş (sadece `__pycache__` kalmış) — eski bir mock üreteci silinmiş; yenisini sıfırdan yazacaksın.
```
