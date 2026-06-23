"""Finance data access — read-only queries against the marts.* schema in
analytics-db. One method per mart slice; the service layer shapes the rows."""

import asyncpg

from ..core.exceptions import UserNotFoundError

_USER_QUERY = """
    SELECT user_id, full_name, income_band
    FROM marts.dim_user
    WHERE user_id = $1
"""

_CASHFLOW_QUERY = """
    SELECT txn_month, total_income, total_spend, net_cashflow
    FROM marts.fct_monthly_cashflow
    WHERE user_id = $1
    ORDER BY txn_month
"""

_LATEST_MONTH_QUERY = """
    SELECT max(txn_month) AS latest_month
    FROM marts.fct_monthly_cashflow
    WHERE user_id = $1
"""

_SPENDING_QUERY = """
    SELECT group_name, total_spend, txn_count
    FROM marts.fct_monthly_spending
    WHERE user_id = $1 AND txn_month = $2
    ORDER BY total_spend DESC
"""

_NET_WORTH_QUERY = """
    SELECT balance_month, net_worth
    FROM marts.fct_net_worth_monthly
    WHERE user_id = $1
    ORDER BY balance_month
"""

_PEER_QUERY = """
    SELECT income_band, txn_month, total_spend, peer_avg_spend, spend_vs_peer, pct_of_peer
    FROM marts.mart_peer_comparison
    WHERE user_id = $1
    ORDER BY txn_month DESC
    LIMIT 1
"""


class FinanceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_user(self, user_id: int) -> dict:
        """Return one user's dimension row. Raises UserNotFoundError."""
        row = await self._pool.fetchrow(_USER_QUERY, user_id)
        if row is None:
            raise UserNotFoundError(user_id)
        return dict(row)

    async def latest_month(self, user_id: int) -> "date | None":
        return await self._pool.fetchval(_LATEST_MONTH_QUERY, user_id)

    async def get_cashflow(self, user_id: int) -> list[dict]:
        rows = await self._pool.fetch(_CASHFLOW_QUERY, user_id)
        return [dict(r) for r in rows]

    async def get_spending(self, user_id: int, month) -> list[dict]:
        rows = await self._pool.fetch(_SPENDING_QUERY, user_id, month)
        return [dict(r) for r in rows]

    async def get_net_worth(self, user_id: int) -> list[dict]:
        rows = await self._pool.fetch(_NET_WORTH_QUERY, user_id)
        return [dict(r) for r in rows]

    async def get_peer_comparison(self, user_id: int) -> dict | None:
        row = await self._pool.fetchrow(_PEER_QUERY, user_id)
        return dict(row) if row else None
