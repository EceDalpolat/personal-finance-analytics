"""Reads mart_ai_context — the dbt model that summarises each user for the AI.
Read-only access to analytics-db."""

import asyncpg

from ..core.exceptions import ContextNotFoundError

_CONTEXT_QUERY = """
    SELECT user_id, income_band, latest_month,
           last_month_income, last_month_spend, last_month_net,
           top_category, top_category_spend,
           over_budget_count, over_budget_categories,
           net_worth_latest, net_worth_6m_ago, net_worth_6m_change,
           peer_avg_spend, pct_of_peer,
           monthly_spend_6m, category_breakdown
    FROM ai_layer.mart_ai_context
    WHERE user_id = $1
"""


class ContextRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_user_context(self, user_id: int) -> dict:
        """Return one user's AI context as a dict. Raises ContextNotFoundError."""
        row = await self._pool.fetchrow(_CONTEXT_QUERY, user_id)
        if row is None:
            raise ContextNotFoundError(user_id)
        return dict(row)

    async def list_user_ids(self) -> list[int]:
        rows = await self._pool.fetch("SELECT user_id FROM ai_layer.mart_ai_context ORDER BY user_id")
        return [r["user_id"] for r in rows]
