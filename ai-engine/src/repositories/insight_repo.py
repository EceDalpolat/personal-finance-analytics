"""Writes generated insights to the app-owned ai.insights table (not dbt-managed)."""

from datetime import date

import asyncpg

_INSERT = """
    INSERT INTO ai.insights (user_id, insight_type, period_month, title, body, model)
    VALUES ($1, $2, $3, $4, $5, $6)
    RETURNING insight_id
"""


class InsightRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add_insight(
        self,
        *,
        user_id: int,
        insight_type: str,
        title: str,
        body: str,
        model: str,
        period_month: date | None = None,
    ) -> int:
        return await self._pool.fetchval(
            _INSERT, user_id, insight_type, period_month, title, body, model
        )
