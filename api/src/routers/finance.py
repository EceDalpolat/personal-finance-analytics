"""Finance router — read-only endpoints over the user's mart data."""

from fastapi import APIRouter

from ..dependencies import FinanceServiceDep
from ..schemas.finance import (
    CashflowSeries,
    NetWorthSeries,
    PeerComparison,
    SpendingBreakdown,
    UserSummary,
)

router = APIRouter(prefix="/finance/users/{user_id}", tags=["finance"])


@router.get("/summary", response_model=UserSummary)
async def summary(user_id: int, service: FinanceServiceDep) -> UserSummary:
    return await service.get_summary(user_id)


@router.get("/cashflow", response_model=CashflowSeries)
async def cashflow(user_id: int, service: FinanceServiceDep) -> CashflowSeries:
    return await service.get_cashflow(user_id)


@router.get("/spending", response_model=SpendingBreakdown)
async def spending(user_id: int, service: FinanceServiceDep) -> SpendingBreakdown:
    return await service.get_spending(user_id)


@router.get("/net-worth", response_model=NetWorthSeries)
async def net_worth(user_id: int, service: FinanceServiceDep) -> NetWorthSeries:
    return await service.get_net_worth(user_id)


@router.get("/peer-comparison", response_model=PeerComparison)
async def peer_comparison(user_id: int, service: FinanceServiceDep) -> PeerComparison:
    return await service.get_peer_comparison(user_id)
