# dbt Pipeline — Sıfırdan Anlatım (Tam Rehber)

> Amaç: Bu dosyayı okuyan biri, projedeki dbt pipeline'ını **sıfırdan kendi
> yazabilecek** seviyede anlasın. Her dosya, her SQL bloğu için **ne / neden /
> nasıl** açıklanır. Hiçbir kısım atlanmaz.

İçindekiler:
1. [dbt'nin zihinsel modeli](#1-dbtnin-zihinsel-modeli)
2. [Katman felsefesi ve materialization](#2-katman-felsefesi-ve-materialization)
3. [Config dosyaları](#3-config-dosyaları)
4. [sources — ham veri tanımı](#4-sources--ham-veri-tanımı)
5. [staging — temizleme katmanı](#5-staging--temizleme-katmanı)
6. [intermediate — iş mantığı](#6-intermediate--iş-mantığı)
7. [marts/finance — iş-hazır tablolar](#7-martsfinance--iş-hazır-tablolar)
8. [marts/ai_layer — AI bağlamı](#8-martsai_layer--ai-bağlamı)
9. [macros](#9-macros)
10. [testler](#10-testler)
11. [DAG, çalıştırma, doğrulama](#11-dag-çalıştırma-doğrulama)
12. [Sıfırdan nasıl yazardın — özet reçete](#12-sıfırdan-nasıl-yazardın--özet-reçete)

---

## 1. dbt'nin zihinsel modeli

dbt tek bir iş yapar: **yazdığın `SELECT` cümlesini veritabanında bir tablo ya
da view'a dönüştürür.** Sen asla `CREATE TABLE`, `DROP`, `INSERT` yazmazsın.
Sadece "bu modelin içeriği şu sorgunun sonucudur" dersin; gerisini (oluşturma,
silme, sıralama) dbt halleder.

Her şeyin temelinde **iki Jinja fonksiyonu** var:

| Fonksiyon | Anlamı | Örnek |
|-----------|--------|-------|
| `{{ source('core', 'transactions') }}` | "Şu ham kaynak tabloya işaret et" | FDW'deki `raw_core.transactions` |
| `{{ ref('stg_core__transactions') }}` | "Şu dbt modeline işaret et" | Başka bir `.sql` model |

**Neden düz string değil de fonksiyon?** Çünkü dbt bu çağrıları tarayıp
**bağımlılık grafiğini (DAG — Directed Acyclic Graph)** otomatik çıkarır. Sen
"önce A sonra B çalışsın" demezsin; dbt `ref()`'lere bakar, kim kime bağlı
anlar, doğru sırayı kendi kurar. Yani `dbt build` derken staging → intermediate
→ marts sırası **senin yazdığın `ref()`'lerden türüyor**, elle tanımlanmıyor.

Bir başka kazanç: `ref()` aynı zamanda **şema/isim soyutlaması**. Modelin gerçek
adı `analytics.staging.stg_core__transactions` olabilir ama sen sadece
`ref('stg_core__transactions')` yazarsın; şema değişse de SQL'in kırılmaz.

---

## 2. Katman felsefesi ve materialization

Veri ham halden iş-hazır hale **katman katman** ilerler (medallion benzeri):

```
sources       →  ham tabloların TANIMI (tablo oluşturmaz, "şu tablo var" der)
   ↓ source()
staging        →  kaynakla 1:1, sadece temizle (rename + cast).   view
   ↓ ref()
intermediate   →  iş mantığı (join, aggregate, hesap).            ephemeral
   ↓ ref()
marts          →  dashboard'un okuduğu son tablolar.              table
```

**Materialization = dbt'nin SELECT'ini fiziksel olarak nasıl sakladığı.** Katmana
göre farklı seçtik, hepsinin bir nedeni var:

| Materialization | Ne yapar | Hangi katman | Neden |
|-----------------|----------|--------------|-------|
| `view` | DB'de bir VIEW oluşturur; veriyi saklamaz, her sorguda kaynaktan okur | staging | Staging hafif (sadece rename/cast). Disk yemesin, hep güncel olsun. |
| `ephemeral` | **Hiçbir fiziksel nesne oluşturmaz**; modelin SQL'i, onu `ref()` eden modelin içine **CTE olarak gömülür** | intermediate | Ara hesaplar veritabanını şişirmesin; sadece mantığı modülerleştirsin. |
| `table` | Gerçek bir TABLE oluşturur; `dbt run`'da bir kez hesaplanıp saklanır | marts | Superset hızlı okusun diye önceden materialize edilir. |

> **Ephemeral'i sindir:** `int_finance__transactions_enriched` ephemeral. Onu
> `fct_monthly_spending` `ref()` ediyor. dbt, intermediate modelin SQL'ini bir
> CTE olarak mart'ın sorgusunun başına yapıştırır. Veritabanında
> `int_finance__transactions_enriched` diye bir tablo **yoktur** — sadece
> derleme anında var olur. Bu yüzden `\dt` çıktısında intermediate görmedik.

---

## 3. Config dosyaları

### 3.1 `dbt/dbt_project.yml` — projenin beyni

```yaml
name: 'finance_analytics'
version: '1.0.0'
profile: 'finance_analytics'   # profiles.yml içindeki hangi bağlantıyı kullansın
config-version: 2

model-paths: ["models"]         # modeller nerede
seed-paths: ["seeds"]
macro-paths: ["macros"]
test-paths: ["tests"]
snapshot-paths: ["snapshots"]

clean-targets: ["target", "dbt_packages"]   # `dbt clean` neyi silsin

models:
  finance_analytics:            # <- proje adıyla aynı olmalı
    staging:
      +materialized: view        # staging/ altındaki HER model view
      +schema: staging
    intermediate:
      +materialized: ephemeral
    marts:
      +materialized: table
      finance:   { +schema: marts }
      ai_layer:  { +schema: ai_layer }
```

- **Ne:** Klasör yolu → materialization + şema eşlemesi.
- **Neden:** Her `.sql` dosyasının tepesine `{{ config(materialized='view') }}`
  yazmak yerine kuralı **klasör bazında bir kez** tanımlarsın (DRY). Bir model
  istisna isterse kendi içinde `{{ config(...) }}` ile override eder
  (mart_ai_insights'ta yaptık: marts default `table` ama onu `view` yaptık).
- **Nasıl:** `+` öneki "bu seviye ve altındaki her şeye uygula" demek.
  `models.finance_analytics` altındaki anahtarlar `models/` içindeki klasör
  adlarıyla eşleşir.

### 3.2 `dbt/profiles.yml` — veritabanı bağlantısı

```yaml
finance_analytics:
  target: dev                    # varsayılan ortam
  outputs:
    dev:
      type: postgres
      host: "{{ env_var('ANALYTICS_DB_HOST', 'analytics-db') }}"
      port: "{{ env_var('ANALYTICS_DB_PORT', '5432') | int }}"
      user: "{{ env_var('ANALYTICS_DB_USER', 'analytics') }}"
      password: "{{ env_var('ANALYTICS_DB_PASSWORD', 'changeme') }}"
      dbname: "{{ env_var('ANALYTICS_DB_NAME', 'analytics') }}"
      schema: analytics          # hedef (varsayılan) şema
      threads: 4                 # paralel kaç model çalışsın
      sslmode: disable
```

- **Ne:** dbt hangi DB'ye, hangi kullanıcıyla bağlanacak.
- **Neden ayrı dosya + `env_var()`:** Bağlantı bilgisi koddan ayrı; secret'lar
  ortamdan gelir, dosyada hardcoded durmaz (CLAUDE.md güvenlik kuralı).
  `env_var('X', 'default')` → ortamda yoksa default kullan.
- **Nasıl:** Compose `dbt` servisine `ANALYTICS_DB_*` env'lerini verir;
  `DBT_PROFILES_DIR=/app` ile dbt bu dosyayı bulur. `schema: analytics`
  "özel şema belirtilmemiş modeller buraya gitsin" demek.

### 3.3 `dbt/macros/generate_schema_name.sql` — temiz şema adları

```jinja
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema | trim }}        {# özel şema yoksa: analytics #}
    {%- else -%}
        {{ custom_schema_name | trim }}   {# özel şema varsa: OLDUĞU GİBİ kullan #}
    {%- endif -%}
{%- endmacro %}
```

- **Sorun:** dbt'nin **varsayılan** `generate_schema_name`'i, `+schema: staging`
  dediğinde şemayı `analytics_staging` yapar (hedef_şema + "_" + özel_ad). Çirkin.
- **Çözüm:** Aynı isimde macro tanımlayınca dbt **kendi default'u yerine seninkini**
  çağırır (override). Biz "özel şema adını birebir kullan" dedik → şemalar
  `staging`, `marts`, `ai_layer` oldu.
- **Nasıl:** dbt'de bazı macro'lar "override edilebilir hook"tur;
  `generate_schema_name` bunlardan biri. Aynı isimle yeniden tanımla, gerisi olur.

### 3.4 `dbt/packages.yml` — dış paketler

```yaml
packages:
  - package: dbt-labs/dbt_utils
    version: [">=1.1.0", "<2.0.0"]
```

- **Ne:** `dbt_utils` paketini projeye ekler.
- **Neden:** Hazır test/macro'lar için — biz `dbt_utils.unique_combination_of_columns`
  testini kullandık (birden çok kolonun birlikte benzersizliği).
- **Nasıl:** `dbt deps` komutu bunu indirir → `dbt_packages/` klasörü (gitignore'da).

### 3.5 `dbt/Dockerfile` + compose `dbt` servisi

```dockerfile
FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "dbt-postgres==1.9.0"   # bu, dbt-core 1.11'i de çeker
COPY . .
RUN dbt deps
ENV DBT_PROFILES_DIR=/app
ENTRYPOINT ["dbt"]        # böylece `... dbt build` = `dbt build`
CMD ["build"]
```

- **Neden Docker:** Lokalde dbt kurmana gerek yok; herkeste ve CI'da **aynı
  versiyon** → reprodüklenebilirlik. `dbt-postgres==1.9.0` pinli olduğu için
  sürpriz yok.
- **İncelik (volume gölgeleme):** Compose'da `./dbt:/app` mount'u, image içine
  build sırasında inen `dbt_packages`'i **gölgeler** (host klasörü üstüne biner).
  Bu yüzden ilk kullanımda runtime'da bir kez `docker compose run --rm dbt deps`
  çalıştırıp paketleri host'taki `dbt/dbt_packages/`'e indiriyoruz.

---

## 4. sources — ham veri tanımı

Dosya: `dbt/models/sources/sources.yml`

`source`, **tablo oluşturmaz**. Sadece "veritabanında şu şemada şu tablolar var,
ben bunlara `source()` ile erişeceğim" diye **bildirir** ve üstlerine **test**
ekler.

```yaml
version: 2
sources:
  - name: core                  # source('core', ...) ile çağrılır
    schema: raw_core            # gerçek şema adı (FDW foreign tabloları)
    tables:
      - name: users
        columns:
          - name: user_id
            tests: [not_null, unique]
          - name: income_band
            tests:
              - accepted_values: { values: ['low', 'mid', 'high'] }
      - name: transactions
        columns:
          - name: account_id
            tests:
              - not_null
              - relationships: { to: "source('core', 'accounts')", field: account_id }
      ...
  - name: ai
    schema: ai
    tables:
      - name: insights          # ai-engine'in yazdığı tablo
```

- **`name: core` + `schema: raw_core`:** Mantıksal ad `core`, fiziksel şema
  `raw_core`. Modelde `source('core', 'transactions')` yazarsın, dbt onu
  `raw_core.transactions`'a çevirir. Soyutlama: yarın şema adı değişse tek yerden
  düzeltirsin.
- **Neden source katmanı:** (1) Tek doğruluk noktası — tüm ham tablolar burada
  belgelenir. (2) Veri **kapıda** test edilir: `relationships` testi, FDW'den gelen
  veride bozuk foreign key var mı diye **kaynağın kendisinde** kontrol eder.
- **Test türleri:**
  - `not_null` / `unique` → kolon kısıtı.
  - `accepted_values` → kolon sadece şu değerleri alabilir (örn. `income_band ∈ {low,mid,high}`).
  - `relationships` → her `transactions.account_id`, `accounts.account_id`'de
    karşılığı var mı (yetim kayıt yok mu). Bu **referans bütünlüğü** testi.
- **YAML tuzağı (yaşadık!):** `{ to: source('core', 'users'), field: ... }` —
  buradaki `source(...)` içindeki **virgül**, YAML flow-mapping'de ayırıcı sanılır
  ve parse patlar. Çözüm: ifadeyi **tırnağa al** → `to: "source('core', 'users')"`.
- **`ai` source'u:** `ai.insights` dbt tarafından YÖNETİLMEZ (onu ai-engine yazar).
  Onu source olarak tanımlayıp `mart_ai_insights` view'ı ile sadece **okuruz**.

---

## 5. staging — temizleme katmanı

Konum: `dbt/models/staging/`. Kural: **kaynakla 1:1, sadece rename + cast.** İş
mantığı (join/aggregate) YOK. Materialization: `view`.

**Neden bu disiplin?** Her ham tabloya tek bir "temiz giriş kapısı" olur. Sonraki
katmanlar asla doğrudan `source()` kullanmaz; hep staging'i `ref()` eder. Böylece
bir kolonu yeniden adlandırmak/cast etmek istersen **tek yerde** yaparsın.

Örnek — `stg_core__transactions.sql`:

```sql
with source as (
    select * from {{ source('core', 'transactions') }}   -- tek source() burada
)
select
    transaction_id,
    account_id,
    category_id,
    merchant_id,
    txn_ts,
    cast(txn_ts as date)               as txn_date,        -- türetilen kolon
    date_trunc('month', txn_ts)::date  as txn_month,       -- ayın ilk günü
    direction,
    amount,
    currency,
    description
from source
```

- **`with source as (select * from {{ source(...) }})`:** Yaygın dbt kalıbı.
  source çağrısını tek bir CTE'ye hapseder; alt sorgu onu kullanır. Okunur + tek noktada.
- **`txn_date`, `txn_month`:** Hafif türetmeler staging'de yapılır (cast/format
  "temizleme" sayılır). `date_trunc('month', ts)::date` = "2026-05-17" → "2026-05-01".
  Aylık gruplamaların hepsi bu kolona dayanacak; bir kez burada üretip her yerde
  kullanırız.
- **Adlandırma `stg_{source}__{entity}`:** `stg_core__transactions`. Çift alt çizgi
  kaynak ile varlığı ayırır. CLAUDE.md konvansiyonu.

8 staging modelinin hepsi aynı kalıpta:

| Model | Ne yapar |
|-------|----------|
| `stg_core__users` | users 1:1 |
| `stg_core__accounts` | accounts 1:1 |
| `stg_core__categories` | `name` → `category_name` rename |
| `stg_core__merchants` | `name` → `merchant_name` rename |
| `stg_core__transactions` | + `txn_date`, `txn_month` türetir |
| `stg_core__budgets` | budgets 1:1 |
| `stg_core__account_balances` | + `balance_month` türetir |
| `stg_core__holdings` | holdings 1:1 |

> Neden `name` → `category_name`? Çünkü ileride join'lerde `categories.name` ve
> `merchants.name` çakışır. Staging'de net adlar verince mart SQL'leri okunur olur.

---

## 6. intermediate — iş mantığı

Konum: `dbt/models/intermediate/`. Burada **gerçek hesap** başlar: join, aggregate,
case. Materialization: `ephemeral` (fiziksel tablo yok, CTE olarak gömülür).

### 6.1 `int_finance__transactions_enriched.sql` — pipeline'ın beli

Her işleme; sahibi (user), kategorisi (ad + tür) ve **üst grubu** eklenir. Diğer
tüm hesaplar buradan beslenir.

```sql
with txns as (
    select * from {{ ref('stg_core__transactions') }}
),
accounts as (
    select account_id, user_id from {{ ref('stg_core__accounts') }}
),
categories as (
    select category_id, category_name, parent_category_id, kind
    from {{ ref('stg_core__categories') }}
)
select
    t.transaction_id,
    a.user_id,                                          -- işlem -> hesap -> kullanıcı
    t.account_id,
    t.txn_month,
    t.direction,
    t.amount,
    t.category_id,
    c.category_name,
    c.kind                                        as category_kind,   -- expense / income
    coalesce(c.parent_category_id, c.category_id) as group_id,         -- ÜST GRUP
    g.category_name                               as group_name
from txns t
join accounts a   on a.account_id = t.account_id        -- kullanıcıyı bul
join categories c on c.category_id = t.category_id       -- yaprak kategori
left join categories g                                   -- grubun ADINI bul (self-join)
    on g.category_id = coalesce(c.parent_category_id, c.category_id)
```

- **Neden user_id'yi burada ekliyoruz?** `transactions` tablosunda `user_id`
  **yok** — sadece `account_id` var. Kullanıcı bazlı her analiz için önce
  `accounts` ile join'leyip `user_id`'yi getirmemiz lazım. Bunu bir kez burada
  yapıp herkese sunuyoruz.
- **`coalesce(c.parent_category_id, c.category_id) as group_id` — en kritik satır:**
  Kategoriler 2 seviyeli: gruplar (Food=2, parent NULL) ve yapraklar (Groceries=201,
  parent=2). Bir işlem hep yaprak kategoriye bağlı. "Bu işlem hangi gruba ait?"
  sorusunun cevabı = yaprağın parent'ı. Ama bir işlem doğrudan bir gruba da bağlı
  olabilir (parent NULL), o zaman grup = kendisi. `coalesce(parent, self)` tam
  bunu yapar: "parent varsa onu, yoksa kendini grup say".
- **`left join categories g` (self-join):** `categories` tablosunu **ikinci kez**
  `g` takma adıyla join'leyerek grubun **adını** (`group_name`) getiriyoruz. Aynı
  tabloyu kendisiyle join'lemek = "self-join". `left` çünkü grup bulunamasa bile
  işlem düşmesin.
- **Neden ephemeral:** Bu model 86 bin satırlık dev bir join; ama tek başına
  dashboard'a gitmez, sadece aşağıdakileri besler. Fiziksel tablo yapmaya gerek
  yok → CTE olarak gömülür.

### 6.2 `int_finance__monthly_category_spend.sql` — aylık grup harcaması

```sql
select
    user_id,
    txn_month,
    group_id,
    group_name,
    sum(amount) as total_spend,
    count(*)    as txn_count
from {{ ref('int_finance__transactions_enriched') }}
where direction = 'debit' and category_kind = 'expense'    -- sadece GİDER
group by 1, 2, 3, 4
```

- **Ne:** Kullanıcı × ay × kategori-grubu bazında toplam harcama.
- **Neden grup grain'i?** Çünkü **bütçeler grup seviyesinde** (Food, Transport...).
  Harcamayı da grup bazında toplarsak, ikisini doğrudan kıyaslayabiliriz (Bölüm 7.5).
- **`where direction='debit' and category_kind='expense'`:** Para çıkışı VE gider
  türü. Maaş (credit/income) buraya girmesin.
- **`group by 1,2,3,4`:** Pozisyonel gruplama — select'teki ilk 4 kolona göre grupla.

### 6.3 `int_finance__monthly_cashflow.sql` — gelir vs gider

```sql
select
    user_id,
    txn_month,
    sum(case when direction='credit' and category_kind='income'  then amount else 0 end) as total_income,
    sum(case when direction='debit'  and category_kind='expense' then amount else 0 end) as total_spend,
    sum(case when direction='credit' and category_kind='income'  then amount else 0 end)
      - sum(case when direction='debit' and category_kind='expense' then amount else 0 end) as net_cashflow
from {{ ref('int_finance__transactions_enriched') }}
group by 1, 2
```

- **`sum(case when ... then amount else 0 end)` — koşullu toplam (pivot kalıbı):**
  Tek geçişte hem geliri hem gideri ayrı ayrı toplar. `case` her satır için
  "bu satır gelir mi gider mi" karar verir; gelir satırında gider toplamına 0
  ekler. Bu, "conditional aggregation" — SQL'de çok kullanılan güçlü bir kalıp.
- **`net_cashflow`:** gelir − gider. Pozitifse o ay para biriktirmiş.
- **Neden ayrı model (spend zaten vardı)?** `monthly_category_spend` kategori
  kırılımlı; bu ise kullanıcı×ay'da **tek satır** (toplam gelir/gider/net). Farklı
  grain → farklı model. mart_ai_context ve peer karşılaştırması bunu kullanır.

### 6.4 `int_finance__net_worth_monthly.sql` — net değer

```sql
with balances as (
    select * from {{ ref('stg_core__account_balances') }}
),
accounts as (
    select account_id, user_id from {{ ref('stg_core__accounts') }}
)
select
    a.user_id,
    b.balance_month,
    sum(b.balance) as net_worth        -- kullanıcının TÜM hesaplarının toplamı
from balances b
join accounts a on a.account_id = b.account_id
group by 1, 2
```

- **Ne:** Kullanıcı × ay → tüm hesap bakiyelerinin toplamı = net değer.
- **Neden join accounts:** Bakiyeler `account_id` bazında; kullanıcıya çıkmak için
  yine accounts join'i gerekiyor (transactions'taki gibi).
- **İncelik:** Kredi kartı bakiyeleri **negatif** (borç) üretiliyor, dolayısıyla
  `sum` otomatik olarak borcu net değerden düşer. Ekstra mantık gerekmedi.

---

## 7. marts/finance — iş-hazır tablolar

Konum: `dbt/models/marts/finance/`. Materialization: `table`. Dashboard buradan
okur. İsimlendirme: `dim_*` (boyut), `fct_*` (olgu/fact), `mart_*` (birleşik).

### 7.1 `dim_user.sql` — kullanıcı boyutu
```sql
select user_id, full_name, email, country, age_band,
       income_band, employment_status, signup_date
from {{ ref('stg_core__users') }}
```
Basit boyut tablosu. Dashboard'da filtre/segment için.

### 7.2 `dim_category.sql` — kategori boyutu (düzleştirilmiş hiyerarşi)
```sql
with categories as ( select * from {{ ref('stg_core__categories') }} )
select
    c.category_id,
    c.category_name,
    c.kind,
    coalesce(c.parent_category_id, c.category_id) as group_id,
    g.category_name                               as group_name,
    (c.parent_category_id is null)                as is_group     -- bu satır grup mu?
from categories c
left join categories g
    on g.category_id = coalesce(c.parent_category_id, c.category_id)
```
- Yaprak + üst grubu tek satırda düzleştirir (enriched'teki self-join mantığının
  aynısı). `is_group` bayrağı, grup satırlarını yapraklardan ayırır.
- **Neden lazım:** mart_ai_context'te `group_id`'den grup **adına** ulaşmak için
  buna join'liyoruz.

### 7.3 `fct_monthly_spending.sql`
```sql
select user_id, txn_month, group_id, group_name, total_spend, txn_count
from {{ ref('int_finance__monthly_category_spend') }}
```
- İlgili intermediate'i alıp **materialize eder** (table). "Mart neden sadece
  intermediate'i seçiyor?" → intermediate ephemeral (fiziksel değil); dashboard'un
  hızlı okuyabilmesi için onu kalıcı tabloya çeviren katman bu.

### 7.4 `fct_monthly_cashflow.sql`
```sql
select user_id, txn_month, total_income, total_spend, net_cashflow
from {{ ref('int_finance__monthly_cashflow') }}
```
Aynı kalıp — cashflow intermediate'inin materialize edilmiş hali.

### 7.5 `fct_budget_variance.sql` — bütçe vs gerçek (en öğretici mart)
```sql
with budgets as ( select * from {{ ref('stg_core__budgets') }} ),
spend   as ( select * from {{ ref('int_finance__monthly_category_spend') }} )
select
    b.budget_id,
    b.user_id,
    b.category_id                                          as group_id,
    b.period_month,
    b.limit_amount,
    coalesce(s.total_spend, 0)                             as actual_spend,
    round(coalesce(s.total_spend, 0) - b.limit_amount, 2)  as variance,
    round(coalesce(s.total_spend, 0)
          / nullif(b.limit_amount, 0) * 100, 1)            as pct_of_limit,
    {{ budget_status('coalesce(s.total_spend, 0)', 'b.limit_amount') }} as status,
    (coalesce(s.total_spend, 0) > b.limit_amount)          as over_budget
from budgets b
left join spend s
    on  s.user_id   = b.user_id
    and s.group_id  = b.category_id        -- bütçe grup seviyesinde -> harcama grubu
    and s.txn_month = b.period_month
```
- **`budgets` ana tablo (left join):** Her bütçe satırı için gerçek harcamayı
  arıyoruz. `left join` çünkü bir grup için bütçe var ama o ay hiç harcama yoksa
  satır kaybolmasın.
- **`coalesce(s.total_spend, 0)`:** Harcama yoksa NULL gelir; onu 0'a çeviriyoruz
  (yoksa variance hesapları NULL olur).
- **`nullif(b.limit_amount, 0)`:** **Sıfıra bölme koruması.** Limit 0 olursa
  `nullif` onu NULL yapar, bölme NULL döner (hata yerine). Klasik güvenli-bölme kalıbı.
- **`{{ budget_status(...) }}`:** Kendi yazdığımız macro (Bölüm 9). 'over'/'near'/'under'
  etiketi üretir. Eşiğin kuralı tek yerde dursun diye macro.
- **`over_budget` boolean:** Hızlı filtre için (aşan bütçeler).

### 7.6 `fct_net_worth_monthly.sql`
```sql
select user_id, balance_month, net_worth
from {{ ref('int_finance__net_worth_monthly') }}
```
Net değer intermediate'inin materialize hali.

### 7.7 `mart_peer_comparison.sql` — akran kıyaslaması
```sql
with cashflow as (
    select user_id, txn_month, total_spend from {{ ref('int_finance__monthly_cashflow') }}
),
users as (
    select user_id, income_band from {{ ref('stg_core__users') }}
),
joined as (                                  -- harcamaya gelir-bandını ekle
    select cf.user_id, cf.txn_month, cf.total_spend, u.income_band
    from cashflow cf join users u using (user_id)
),
peer as (                                    -- her bant×ay için ORTALAMA harcama
    select income_band, txn_month, avg(total_spend) as peer_avg_spend
    from joined group by 1, 2
)
select
    j.user_id, j.income_band, j.txn_month,
    j.total_spend,
    round(p.peer_avg_spend, 2)                                 as peer_avg_spend,
    round(j.total_spend - p.peer_avg_spend, 2)                 as spend_vs_peer,
    round(j.total_spend / nullif(p.peer_avg_spend, 0) * 100, 1) as pct_of_peer
from joined j
join peer p on p.income_band = j.income_band and p.txn_month = j.txn_month
```
- **Fikir:** "Benzer profildeki (aynı gelir bandı) insanlara göre nasılım?"
- **`peer` CTE:** Aynı gelir-bandındaki herkesin o ayki ortalama harcaması.
  Bu bir **aggregate** — kullanıcı bazını silip bant×ay'a indiriyor.
- **Sonra geri join:** Her kullanıcının kendi harcamasını, ait olduğu bandın
  ortalamasıyla aynı satırda buluşturuyoruz → `spend_vs_peer`, `pct_of_peer`.
- **`using (user_id)`:** `on a.user_id = b.user_id`'nin kısa yazımı (kolon adı
  iki tarafta da aynıysa).

---

## 8. marts/ai_layer — AI bağlamı

Konum: `dbt/models/marts/ai_layer/`. Bu katman **dbt ile AI motoru arasındaki
sözleşme**.

### 8.1 `mart_ai_context.sql` — kullanıcı başına TEK satır özet

Bu modelin amacı: ai-engine'in bir kullanıcı için Claude'a göndereceği **tüm
bağlamı tek satırda** toplamak. ai-engine ham 86 bin işlemi görmez; bu özet
satırı görür → insight'lar tutarlı, denetlenebilir ve ucuz olur.

Yapı (CTE zinciri). Tüm parçalar "en son ay" etrafında döner:

```sql
with months as (
    select max(txn_month) as latest_month from {{ ref('fct_monthly_cashflow') }}
),
```
- **`months`:** Verideki en son ayı bulur (2026-05). Aşağıdaki her CTE buna bağlanıp
  "son ay" verisini çeker. Tek yerde tanımlı.

```sql
cashflow_last as (
    select cf.user_id, cf.total_income, cf.total_spend, cf.net_cashflow
    from {{ ref('fct_monthly_cashflow') }} cf
    join months m on cf.txn_month = m.latest_month
),
```
- Son ayın gelir/gider/net'i (kullanıcı başına).

```sql
top_cat as (
    select distinct on (s.user_id) s.user_id, s.group_name, s.total_spend
    from {{ ref('fct_monthly_spending') }} s
    join months m on s.txn_month = m.latest_month
    order by s.user_id, s.total_spend desc
),
```
- **`distinct on (user_id) ... order by user_id, total_spend desc`:** Postgres'e
  özgü güçlü kalıp. Her `user_id` için, `total_spend`'e göre **en yüksek** satırı
  seçer (her kullanıcının son aydaki en pahalı kategorisi). `distinct on`,
  gruptaki ilk satırı alır; `order by` o "ilk"i belirler.

```sql
budget_last as (
    select
        bv.user_id,
        count(*) filter (where bv.over_budget)               as over_budget_count,
        json_agg(dc.group_name) filter (where bv.over_budget) as over_budget_categories
    from {{ ref('fct_budget_variance') }} bv
    join months m on bv.period_month = m.latest_month
    left join {{ ref('dim_category') }} dc on dc.category_id = bv.group_id
    group by bv.user_id
),
```
- **`count(*) filter (where ...)`:** SQL standardı "filtered aggregate" — sadece
  koşulu sağlayan satırları sayar (son ay aşılan bütçe sayısı).
- **`json_agg(...) filter (...)`:** Aşılan bütçelerin **isimlerini bir JSON
  dizisine** toplar. `dim_category` join'i `group_id` → grup adı dönüşümü için.
- Prompt'ta "Şu kategorilerde bütçeni aştın: [...]" demek için.

```sql
nw_ranked as (
    select user_id, net_worth,
           row_number() over (partition by user_id order by balance_month desc) as rn
    from {{ ref('fct_net_worth_monthly') }}
),
nw_latest as (select user_id, net_worth from nw_ranked where rn = 1),
nw_6m     as (select user_id, net_worth from nw_ranked where rn = 6),
```
- **`row_number() over (partition by user_id order by balance_month desc)`:**
  Pencere fonksiyonu (window function). Her kullanıcının aylarını **en yeniden
  eskiye** sıralayıp numaralandırır: rn=1 en son ay, rn=6 altı ay öncesi.
- **Neden tarih çıkarma yerine `row_number`?** "Son ay − 6 ay" tarih aritmetiği
  ay-sonu tarihlerinde sapabilir; sıralayıp 1. ve 6. satırı almak **sağlam**.
  6'dan az veri varsa rn=6 yoktur → `nw_6m` NULL döner (graceful).

```sql
peer_last as (
    select pc.user_id, pc.peer_avg_spend, pc.pct_of_peer
    from {{ ref('mart_peer_comparison') }} pc
    join months m on pc.txn_month = m.latest_month
),
spend_series as (
    select user_id,
           json_agg(json_build_object('month', txn_month, 'spend', total_spend)
                    order by txn_month) as monthly_spend_6m
    from (
        select user_id, txn_month, total_spend,
               row_number() over (partition by user_id order by txn_month desc) as rn
        from {{ ref('fct_monthly_cashflow') }}
    ) x
    where rn <= 6
    group by user_id
),
cat_breakdown as (
    select s.user_id,
           json_agg(json_build_object('category', s.group_name, 'spend', s.total_spend)
                    order by s.total_spend desc) as category_breakdown
    from {{ ref('fct_monthly_spending') }} s
    join months m on s.txn_month = m.latest_month
    group by s.user_id
)
```
- **`spend_series`:** Son 6 ayın harcama trendi, JSON dizisi olarak
  (`[{"month":..., "spend":...}, ...]`). İç sorgu `row_number` ile son 6 ayı seçer.
- **`cat_breakdown`:** Son ayın kategori kırılımı, JSON. `json_build_object` her
  satırı bir JSON nesnesi yapar; `json_agg` onları diziye toplar (harcamaya göre
  azalan sırada).
- **Neden JSON?** Prompt'a zengin, yapılandırılmış bağlam vermek için. Claude
  "son 6 ayda harcaman şöyle seyretti" diyebilsin.

```sql
select
    u.user_id, u.income_band, m.latest_month,
    cl.total_income  as last_month_income,
    cl.total_spend   as last_month_spend,
    cl.net_cashflow  as last_month_net,
    tc.group_name    as top_category,
    tc.total_spend   as top_category_spend,
    coalesce(bl.over_budget_count, 0) as over_budget_count,
    bl.over_budget_categories,
    nl.net_worth     as net_worth_latest,
    n6.net_worth     as net_worth_6m_ago,
    round(nl.net_worth - n6.net_worth, 2) as net_worth_6m_change,
    pl.peer_avg_spend, pl.pct_of_peer,
    ss.monthly_spend_6m, cb.category_breakdown
from {{ ref('dim_user') }} u
cross join months m                              -- tek satırlık 'months'u herkese ekle
left join cashflow_last cl on cl.user_id = u.user_id
left join top_cat       tc on tc.user_id = u.user_id
left join budget_last   bl on bl.user_id = u.user_id
left join nw_latest     nl on nl.user_id = u.user_id
left join nw_6m         n6 on n6.user_id = u.user_id
left join peer_last     pl on pl.user_id = u.user_id
left join spend_series  ss on ss.user_id = u.user_id
left join cat_breakdown cb on cb.user_id = u.user_id
```
- **`dim_user` ana tablo + hepsi `left join`:** Çıktı **her kullanıcı için tam
  bir satır** olsun diye. Bir kullanıcının (örn.) hiç bütçesi yoksa, o sütun NULL
  kalır ama kullanıcı satırı kaybolmaz.
- **`cross join months`:** `months` tek satır (latest_month). Cross join onu her
  kullanıcı satırına yapıştırır (latest_month kolonu için).
- **Sonuç:** 100 satır, kullanıcı başına 1 — net worth değişimi, top kategori,
  bütçe durumu, akran kıyası ve 2 JSON trend. ai-engine'in ihtiyacı olan her şey.

### 8.2 `mart_ai_insights.sql` — insight'ları sunan view
```sql
{{ config(materialized='view') }}        -- marts default 'table' iken bunu view yap
select insight_id, user_id, insight_type, period_month,
       title, body, model, created_at
from {{ source('ai', 'insights') }}
```
- **Neden view (table değil):** `ai.insights` tablosunu **ai-engine yazıyor**.
  Eğer dbt bunu `table` olarak materialize etseydi, her `dbt run`'da DROP/CREATE
  edip **ai-engine'in yazdığı veriyi silerdi.** View, her sorguda canlı veriyi
  okur — silme yok.
- **`{{ config(...) }}` model içinde:** Klasör kuralını (table) bu modelde
  override etmenin yolu.
- **Mimari ayrım:** dbt'nin yönettiği tablolar (drop/recreate edilebilir) ile
  uygulama-sahipli tablolar (`ai.insights`) ayrı tutulur. dbt sadece okur.

---

## 9. macros

### `dbt/macros/budget_status.sql`
```jinja
{% macro budget_status(actual, budget_limit) -%}
    case
        when {{ actual }} > {{ budget_limit }}        then 'over'
        when {{ actual }} >= 0.9 * {{ budget_limit }} then 'near'
        else 'under'
    end
{%- endmacro %}
```
- **Macro = SQL üreten fonksiyon.** Jinja ile parametre alır, SQL parçası döndürür.
- Çağırınca (`{{ budget_status('coalesce(s.total_spend,0)', 'b.limit_amount') }}`)
  yerine yukarıdaki `case` ifadesi yapıştırılır.
- **Neden:** "Bütçe durumu" mantığı (eşik %90) birden çok mart'ta lazım olabilir;
  tek yerde dursun (DRY). Eşiği değiştireceksen tek dosya.
- Diğer macro `generate_schema_name` (Bölüm 3.3) — dbt'nin davranışını override eden
  özel bir tür.

---

## 10. testler

dbt'de test = "şu sorgu **0 satır** döndürmeli; döndürürse test patlar" mantığı.
İki tür:

**1) Generic testler (YAML'de tanımlı, yeniden kullanılır):**
- `not_null`, `unique` → kolon kısıtı.
- `accepted_values` → kolon sadece izinli değerleri alsın (`status ∈ {over,near,under}`).
- `relationships` → foreign key bütünlüğü (yetim kayıt yok).
- `dbt_utils.unique_combination_of_columns` → **birden çok kolonun birlikte**
  benzersizliği (grain testi). Örn. `fct_monthly_spending`'de
  `[user_id, txn_month, group_id]` kombinasyonu eşsiz olmalı — yani aynı
  kullanıcı/ay/grup iki kez gelmemeli. Bu, modelin **grain'ini (tane boyutunu)**
  garantiler.

Nerede tanımlı: `sources.yml`, `_stg_core__models.yml`, `_finance__models.yml`,
`_ai_layer__models.yml`. (Alt çizgiyle başlayan YAML dosyaları konvansiyon —
"şema/dokümantasyon dosyası" demek.)

**2) Singular testler:** `tests/` klasörüne yazılan tek seferlik özel SQL'ler.
(Bu projede henüz yok; ileride "net worth negatif olmamalı" gibi özel kontroller
buraya gelir.)

**`dbt build` ne yapar:** her modeli oluşturur **ve hemen ardından** o modele
bağlı testleri çalıştırır. Test patlarsa o dalı durdurur. Bizde **88 düğüm
(8 tablo + 9 view + 71 test) PASS**, 0 ERROR.

> **Deprecation uyarısı (hata değil):** dbt 1.11, inline test argümanlarını
> (`{ to: ..., field: ... }`) artık `arguments:` altına almanı öneriyor. Build
> yeşil; ileride istersek temizleriz.

---

## 11. DAG, çalıştırma, doğrulama

**DAG (bağımlılık grafiği)** `ref()`/`source()`'lardan otomatik çıkar:
```
source(core.*)
   └─ stg_core__*                       (8 view)
        └─ int_finance__transactions_enriched
             ├─ int_finance__monthly_category_spend
             │     ├─ fct_monthly_spending
             │     └─ fct_budget_variance  (+ stg_core__budgets)
             ├─ int_finance__monthly_cashflow
             │     ├─ fct_monthly_cashflow
             │     └─ mart_peer_comparison (+ stg_core__users)
             └─ (...)
        └─ int_finance__net_worth_monthly → fct_net_worth_monthly
   dim_user, dim_category
        └─ mart_ai_context  ← tüm finance martlarını birleştirir
source(ai.insights) → mart_ai_insights
```

**Komutlar:**
```bash
docker compose run --rm dbt deps     # paketleri indir (ilk sefer / packages değişince)
docker compose run --rm dbt build    # = run + test, doğru sırada (make dbt-build)
docker compose run --rm dbt run      # sadece modelleri oluştur, test etme
docker compose run --rm dbt test     # sadece testler
docker compose run --rm dbt build --select staging+   # staging ve ardıllarını çalıştır
```
- **`+` operatörü (`state:modified+`, `staging+`):** seçili modelin **ardıllarını**
  da dahil et. `+model` öncülleri, `model+` ardılları.

**Doğrulama (canlı yaptık):**
```bash
docker compose exec analytics-db psql -U analytics -d analytics \
  -c "select * from ai_layer.mart_ai_context where user_id = 1;"
```

---

## 12. Sıfırdan nasıl yazardın — özet reçete

1. **Bağlan:** `dbt_project.yml` (profil adı + klasör materialization'ları) +
   `profiles.yml` (DB bağlantısı, `env_var` ile). Gerekirse `generate_schema_name`
   override (temiz şema adları).
2. **Kaynakları bildir:** `models/sources/*.yml` — şema + tablolar + kolon testleri
   (`unique`, `not_null`, `relationships`, `accepted_values`). Veriyi kapıda doğrula.
3. **Staging yaz:** her kaynak tablo için bir `stg_{src}__{tbl}.sql` — `view`,
   sadece rename/cast, `with source as (select * from {{ source(...) }})` kalıbı.
   İş mantığı YOK.
4. **Intermediate yaz:** join/aggregate burada. `ephemeral`. Önce bir "enriched"
   model (boyutları işleme bağla), sonra grain'e göre aylık/özet modeller.
   `coalesce(parent, self)` ile hiyerarşi rollup, `case when ... then amount`
   ile conditional aggregation gibi kalıpları kullan.
5. **Marts yaz:** `dim_*` (boyut), `fct_*` (grain'li olgu), `mart_*` (birleşik).
   `table`. Intermediate'leri materialize et, kıyas/varyans gibi iş çıktıları üret.
   `nullif(x,0)` ile sıfıra bölmeyi koru, tekrar eden mantığı **macro**'ya al.
6. **AI/sunum katmanı:** Tüketiciye özel tek bir "context" modeli (kullanıcı başına
   1 satır, `left join`'lerle tam satır, JSON aggregate'lerle zengin bağlam).
   Uygulamanın yazdığı tabloları **view** ile oku (dbt yönetmesin).
7. **Test + grain garantisi:** her modele en az grain testi
   (`unique_combination_of_columns`) + anahtar `not_null/unique`.
8. **Çalıştır & doğrula:** `dbt deps` → `dbt build`. DAG'ı dbt kurar; sen sadece
   `ref()`/`source()` doğru yazarsın.

**Akılda kalması gereken 5 fikir:**
- `ref()`/`source()` → DAG'ı ve soyutlamayı bunlar üretir.
- Katman = sorumluluk: staging temizler, intermediate hesaplar, marts sunar.
- Materialization katmana göre: view / ephemeral / table — neden'iyle.
- `coalesce(parent, self)` = hiyerarşi rollup; `case when ... then amount` =
  conditional aggregation; `row_number() over (...)` = "en son/Ninci" seçimi;
  `nullif(x,0)` = güvenli bölme; `json_agg/json_build_object` = zengin bağlam.
- dbt-yönetilen tablo ile uygulama-sahipli tabloyu ayır (`ai.insights` view ile okunur).
