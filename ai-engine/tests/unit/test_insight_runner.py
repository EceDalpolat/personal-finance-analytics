"""InsightRunner unit test — Claude is mocked (per CLAUDE.md: never hit the real
API in tests). Verifies the read -> render -> generate -> store orchestration."""

from datetime import date

from src.runners.insight_runner import InsightRunner
from src.services.context_builder import ContextBuilder

CTX = {
    "user_id": 1, "income_band": "mid", "latest_month": date(2026, 5, 1),
    "last_month_income": 6441.28, "last_month_spend": 3344.58, "last_month_net": 3096.70,
    "top_category": "Housing", "top_category_spend": 1740.47,
    "over_budget_count": 0, "over_budget_categories": None,
    "net_worth_latest": 115156.23, "net_worth_6m_ago": 91288.50, "net_worth_6m_change": 23867.73,
    "peer_avg_spend": 4094.69, "pct_of_peer": 81.7,
    "monthly_spend_6m": "[]", "category_breakdown": "[]",
}


class FakeContextRepo:
    async def get_user_context(self, user_id): return dict(CTX, user_id=user_id)
    async def list_user_ids(self): return [1, 2]


class FakeInsightRepo:
    def __init__(self): self.saved = []
    async def add_insight(self, **kw):
        self.saved.append(kw)
        return len(self.saved)


class FakeClaude:
    model = "claude-sonnet-4-6"
    def __init__(self): self.calls = []
    async def generate_structured(self, *, system, prompt, schema):
        self.calls.append(prompt)
        return {"title": "You saved 48% of income", "body": "Net cashflow was strong."}


async def test_generate_for_user_stores_insight():
    repo = FakeInsightRepo()
    claude = FakeClaude()
    runner = InsightRunner(FakeContextRepo(), repo, ContextBuilder(), claude)

    insight_id = await runner.generate_for_user(1, "monthly")

    assert insight_id == 1
    assert repo.saved[0]["title"] == "You saved 48% of income"
    assert repo.saved[0]["insight_type"] == "monthly"
    assert repo.saved[0]["model"] == "claude-sonnet-4-6"
    assert repo.saved[0]["period_month"] == date(2026, 5, 1)
    # the rendered prompt actually used the context numbers
    assert "Housing" in claude.calls[0]


async def test_run_all_iterates_users():
    repo = FakeInsightRepo()
    runner = InsightRunner(FakeContextRepo(), repo, ContextBuilder(), FakeClaude())

    count = await runner.run_all("recommendation")

    assert count == 2
    assert {s["insight_type"] for s in repo.saved} == {"recommendation"}
