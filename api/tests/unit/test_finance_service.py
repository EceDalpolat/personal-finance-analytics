"""FinanceService unit test — fake repository, no DB. Verifies the service
shapes mart rows into the public schemas and surfaces unknown users as 404s."""

from datetime import date

import pytest

from src.core.exceptions import UserNotFoundError
from src.services.finance_service import FinanceService


class FakeRepo:
    async def get_user(self, user_id):
        return {"full_name": "Ada Lovelace", "income_band": "mid"}

    async def latest_month(self, user_id):
        return date(2026, 5, 1)

    async def get_cashflow(self, user_id):
        return [
            {"txn_month": date(2026, 4, 1), "total_income": 5000, "total_spend": 3000, "net_cashflow": 2000},
            {"txn_month": date(2026, 5, 1), "total_income": 6000, "total_spend": 3500, "net_cashflow": 2500},
        ]

    async def get_net_worth(self, user_id):
        return [
            {"balance_month": date(2026, 4, 1), "net_worth": 90000},
            {"balance_month": date(2026, 5, 1), "net_worth": 115000},
        ]

    async def get_spending(self, user_id, month):
        return [
            {"group_name": "Housing", "total_spend": 1700, "txn_count": 3},
            {"group_name": "Food", "total_spend": 800, "txn_count": 20},
        ]

    async def get_peer_comparison(self, user_id):
        return None


class MissingUserRepo(FakeRepo):
    async def get_user(self, user_id):
        raise UserNotFoundError(user_id)


async def test_summary_uses_latest_month_rows():
    summary = await FinanceService(FakeRepo()).get_summary(1)

    assert summary.full_name == "Ada Lovelace"
    assert summary.latest_month == date(2026, 5, 1)
    assert summary.last_month_income == 6000
    assert summary.last_month_net == 2500
    assert summary.net_worth_latest == 115000


async def test_spending_breakdown_sorted_for_latest_month():
    breakdown = await FinanceService(FakeRepo()).get_spending(1)

    assert breakdown.month == date(2026, 5, 1)
    assert breakdown.categories[0].category == "Housing"
    assert breakdown.categories[0].txn_count == 3


async def test_unknown_user_raises():
    with pytest.raises(UserNotFoundError):
        await FinanceService(MissingUserRepo()).get_summary(999)
