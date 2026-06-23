"""Finance endpoint schemas. Shapes the marts.* mart rows into a stable public
contract (the DB column names stay internal to the repository layer)."""

from datetime import date

from pydantic import BaseModel


class UserSummary(BaseModel):
    user_id: int
    full_name: str
    income_band: str
    latest_month: date | None
    last_month_income: float | None
    last_month_spend: float | None
    last_month_net: float | None
    net_worth_latest: float | None


class CashflowPoint(BaseModel):
    month: date
    income: float
    spend: float
    net: float


class CashflowSeries(BaseModel):
    user_id: int
    points: list[CashflowPoint]


class CategorySpend(BaseModel):
    category: str
    spend: float
    txn_count: int


class SpendingBreakdown(BaseModel):
    user_id: int
    month: date | None
    categories: list[CategorySpend]


class NetWorthPoint(BaseModel):
    month: date
    net_worth: float


class NetWorthSeries(BaseModel):
    user_id: int
    points: list[NetWorthPoint]


class PeerComparison(BaseModel):
    user_id: int
    month: date | None
    income_band: str | None
    total_spend: float | None
    peer_avg_spend: float | None
    spend_vs_peer: float | None
    pct_of_peer: float | None
