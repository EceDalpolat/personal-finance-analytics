"""Finance business logic: pull mart rows via the repository and shape them
into the public finance schemas."""

from ..repositories.finance_repo import FinanceRepository
from ..schemas.finance import (
    CashflowPoint,
    CashflowSeries,
    CategorySpend,
    NetWorthPoint,
    NetWorthSeries,
    PeerComparison,
    SpendingBreakdown,
    UserSummary,
)


class FinanceService:
    def __init__(self, repo: FinanceRepository) -> None:
        self._repo = repo

    async def get_summary(self, user_id: int) -> UserSummary:
        user = await self._repo.get_user(user_id)
        latest_month = await self._repo.latest_month(user_id)
        cashflow = await self._repo.get_cashflow(user_id)
        net_worth = await self._repo.get_net_worth(user_id)
        last = cashflow[-1] if cashflow else None
        return UserSummary(
            user_id=user_id,
            full_name=user["full_name"],
            income_band=user["income_band"],
            latest_month=latest_month,
            last_month_income=last["total_income"] if last else None,
            last_month_spend=last["total_spend"] if last else None,
            last_month_net=last["net_cashflow"] if last else None,
            net_worth_latest=net_worth[-1]["net_worth"] if net_worth else None,
        )

    async def get_cashflow(self, user_id: int) -> CashflowSeries:
        await self._repo.get_user(user_id)  # 404 if unknown user
        rows = await self._repo.get_cashflow(user_id)
        points = [
            CashflowPoint(
                month=r["txn_month"],
                income=r["total_income"],
                spend=r["total_spend"],
                net=r["net_cashflow"],
            )
            for r in rows
        ]
        return CashflowSeries(user_id=user_id, points=points)

    async def get_spending(self, user_id: int) -> SpendingBreakdown:
        await self._repo.get_user(user_id)
        month = await self._repo.latest_month(user_id)
        rows = await self._repo.get_spending(user_id, month) if month else []
        categories = [
            CategorySpend(category=r["group_name"], spend=r["total_spend"], txn_count=r["txn_count"])
            for r in rows
        ]
        return SpendingBreakdown(user_id=user_id, month=month, categories=categories)

    async def get_net_worth(self, user_id: int) -> NetWorthSeries:
        await self._repo.get_user(user_id)
        rows = await self._repo.get_net_worth(user_id)
        points = [NetWorthPoint(month=r["balance_month"], net_worth=r["net_worth"]) for r in rows]
        return NetWorthSeries(user_id=user_id, points=points)

    async def get_peer_comparison(self, user_id: int) -> PeerComparison:
        await self._repo.get_user(user_id)
        row = await self._repo.get_peer_comparison(user_id)
        if row is None:
            return PeerComparison(
                user_id=user_id,
                month=None,
                income_band=None,
                total_spend=None,
                peer_avg_spend=None,
                spend_vs_peer=None,
                pct_of_peer=None,
            )
        return PeerComparison(
            user_id=user_id,
            month=row["txn_month"],
            income_band=row["income_band"],
            total_spend=row["total_spend"],
            peer_avg_spend=row["peer_avg_spend"],
            spend_vs_peer=row["spend_vs_peer"],
            pct_of_peer=row["pct_of_peer"],
        )
