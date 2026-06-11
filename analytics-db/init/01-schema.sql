-- ============================================================================
-- analytics-db : foundation schema
-- ----------------------------------------------------------------------------
-- This database is dbt's warehouse. dbt creates its own schemas (staging,
-- intermediate, marts_*, ai_layer) at run time, so we only set up here what
-- dbt does NOT own:
--   1. the postgres_fdw extension (foreign tables wired in 02-setup-fdw.sh)
--   2. the `ai` schema + ai.insights table — the app-owned write target for
--      the ai-engine. dbt must NEVER manage this table (it would drop/recreate
--      it on every run); dbt only READS it through marts/ai_layer/mart_ai_insights.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgres_fdw;

-- ---------------------------------------------------------------------------
-- ai : insights written back by the ai-engine (step 5).
-- No FK to users — that table lives in source-db, reachable only via FDW.
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS ai;

CREATE TABLE IF NOT EXISTS ai.insights (
    insight_id    BIGINT       GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id       INT          NOT NULL,
    insight_type  TEXT         NOT NULL,   -- monthly / anomaly / recommendation
    period_month  DATE,                    -- the month the insight refers to (if any)
    title         TEXT         NOT NULL,
    body          TEXT         NOT NULL,
    model         TEXT         NOT NULL,   -- e.g. claude-sonnet-4-6
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    CONSTRAINT insights_type_chk
        CHECK (insight_type IN ('monthly','anomaly','recommendation'))
);
CREATE INDEX IF NOT EXISTS insights_user_idx ON ai.insights (user_id, created_at DESC);

COMMENT ON TABLE ai.insights IS
    'AI-generated insights, written by ai-engine; read by dbt mart_ai_insights.';
