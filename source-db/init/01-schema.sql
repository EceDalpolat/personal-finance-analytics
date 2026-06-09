-- ============================================================================
-- source-db : raw operational schema for personal finance
-- ----------------------------------------------------------------------------
-- These are the "system of record" tables a real fintech backend would own.
-- analytics-db mounts this schema read-only via postgres_fdw as `raw_core`
-- (step 3); dbt staging models read it as source('core', ...).
--
-- IDs are plain integers (not identity columns) so the deterministic generator
-- in mock-data/ can assign stable values across runs.
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS core;
SET search_path TO core;

-- ---------------------------------------------------------------------------
-- users : one row per customer, with attributes used for peer benchmarking.
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    user_id           INT          PRIMARY KEY,
    full_name         TEXT         NOT NULL,
    email             TEXT         NOT NULL UNIQUE,
    country           TEXT         NOT NULL,
    age_band          TEXT         NOT NULL,   -- 18-25 / 26-35 / 36-45 / 46-55 / 56+
    income_band       TEXT         NOT NULL,   -- low / mid / high  (peer segment)
    employment_status TEXT         NOT NULL,   -- employed / self_employed / student / retired
    signup_date       DATE         NOT NULL,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT users_age_band_chk
        CHECK (age_band IN ('18-25','26-35','36-45','46-55','56+')),
    CONSTRAINT users_income_band_chk
        CHECK (income_band IN ('low','mid','high'))
);
COMMENT ON TABLE  core.users IS 'Customers; income_band/age_band drive peer comparison marts.';

-- ---------------------------------------------------------------------------
-- categories : static reference. 2-level hierarchy via self FK. Seeded in 02.
-- ---------------------------------------------------------------------------
CREATE TABLE categories (
    category_id        INT   PRIMARY KEY,
    name               TEXT  NOT NULL,
    parent_category_id INT   REFERENCES core.categories (category_id),
    kind               TEXT  NOT NULL,
    CONSTRAINT categories_kind_chk CHECK (kind IN ('expense','income'))
);
COMMENT ON TABLE core.categories IS 'Spending/income taxonomy; top-level groups have NULL parent.';

-- ---------------------------------------------------------------------------
-- merchants : static reference. Seeded in 02.
-- ---------------------------------------------------------------------------
CREATE TABLE merchants (
    merchant_id         INT   PRIMARY KEY,
    name                TEXT  NOT NULL,
    default_category_id INT   NOT NULL REFERENCES core.categories (category_id)
);
COMMENT ON TABLE core.merchants IS 'Known merchants and the category they usually map to.';

-- ---------------------------------------------------------------------------
-- accounts : a user's bank/credit/investment accounts.
-- ---------------------------------------------------------------------------
CREATE TABLE accounts (
    account_id    INT          PRIMARY KEY,
    user_id       INT          NOT NULL REFERENCES core.users (user_id),
    account_type  TEXT         NOT NULL,
    institution   TEXT         NOT NULL,
    currency      CHAR(3)      NOT NULL DEFAULT 'USD',
    opened_at     DATE         NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    CONSTRAINT accounts_type_chk
        CHECK (account_type IN ('checking','savings','credit_card','investment'))
);
CREATE INDEX accounts_user_idx ON core.accounts (user_id);
COMMENT ON TABLE core.accounts IS 'Per-user accounts; investment accounts hold rows in core.holdings.';

-- ---------------------------------------------------------------------------
-- transactions : the central fact. ~2 years of activity per user.
-- amount is always positive; direction encodes money in/out.
-- ---------------------------------------------------------------------------
CREATE TABLE transactions (
    transaction_id  BIGINT        PRIMARY KEY,
    account_id      INT           NOT NULL REFERENCES core.accounts (account_id),
    txn_ts          TIMESTAMPTZ   NOT NULL,
    amount          NUMERIC(12,2) NOT NULL,
    direction       TEXT          NOT NULL,
    category_id     INT           NOT NULL REFERENCES core.categories (category_id),
    merchant_id     INT           REFERENCES core.merchants (merchant_id),
    description     TEXT,
    currency        CHAR(3)       NOT NULL DEFAULT 'USD',
    CONSTRAINT transactions_amount_chk    CHECK (amount > 0),
    CONSTRAINT transactions_direction_chk CHECK (direction IN ('debit','credit'))
);
CREATE INDEX transactions_account_ts_idx ON core.transactions (account_id, txn_ts);
CREATE INDEX transactions_category_idx   ON core.transactions (category_id);
COMMENT ON TABLE core.transactions IS 'Money movement; debit = spend/out, credit = income/in.';

-- ---------------------------------------------------------------------------
-- budgets : per-user monthly spending limit per category.
-- ---------------------------------------------------------------------------
CREATE TABLE budgets (
    budget_id     BIGINT        PRIMARY KEY,
    user_id       INT           NOT NULL REFERENCES core.users (user_id),
    category_id   INT           NOT NULL REFERENCES core.categories (category_id),
    period_month  DATE          NOT NULL,           -- first day of the month
    limit_amount  NUMERIC(12,2) NOT NULL,
    currency      CHAR(3)       NOT NULL DEFAULT 'USD',
    CONSTRAINT budgets_limit_chk CHECK (limit_amount > 0),
    CONSTRAINT budgets_unique UNIQUE (user_id, category_id, period_month)
);
CREATE INDEX budgets_user_month_idx ON core.budgets (user_id, period_month);
COMMENT ON TABLE core.budgets IS 'Monthly category budgets; compared against actual spend in marts.';

-- ---------------------------------------------------------------------------
-- account_balances : month-end balance snapshot per account -> net worth.
-- ---------------------------------------------------------------------------
CREATE TABLE account_balances (
    account_id  INT           NOT NULL REFERENCES core.accounts (account_id),
    as_of_date  DATE          NOT NULL,           -- last day of the month
    balance     NUMERIC(14,2) NOT NULL,
    PRIMARY KEY (account_id, as_of_date)
);
COMMENT ON TABLE core.account_balances IS 'Month-end balances; credit_card balances are negative (debt).';

-- ---------------------------------------------------------------------------
-- holdings : positions inside investment accounts (month-end snapshot).
-- ---------------------------------------------------------------------------
CREATE TABLE holdings (
    holding_id    BIGINT         PRIMARY KEY,
    account_id    INT            NOT NULL REFERENCES core.accounts (account_id),
    symbol        TEXT           NOT NULL,
    asset_class   TEXT           NOT NULL,
    quantity      NUMERIC(18,6)  NOT NULL,
    cost_basis    NUMERIC(14,2)  NOT NULL,        -- total invested
    market_value  NUMERIC(14,2)  NOT NULL,        -- value at as_of_date
    as_of_date    DATE           NOT NULL,
    CONSTRAINT holdings_asset_class_chk
        CHECK (asset_class IN ('equity','etf','crypto','bond','cash'))
);
CREATE INDEX holdings_account_date_idx ON core.holdings (account_id, as_of_date);
COMMENT ON TABLE core.holdings IS 'Investment positions valued at each month-end.';
