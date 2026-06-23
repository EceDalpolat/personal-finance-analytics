"""Insight trigger endpoints. Called after dbt build (run all) or for one user."""

from fastapi import APIRouter, Query

from ..dependencies import InsightRunnerDep
from ..schemas.insight import InsightRunResponse, InsightType

router = APIRouter(prefix="/insights", tags=["insights"])


@router.post("/run", response_model=InsightRunResponse)
async def run_insights(
    runner: InsightRunnerDep,
    insight_type: InsightType = Query("monthly", alias="type"),
) -> InsightRunResponse:
    count = await runner.run_all(insight_type)
    return InsightRunResponse(generated=count, insight_type=insight_type)


@router.post("/user/{user_id}", response_model=InsightRunResponse)
async def run_for_user(
    user_id: int,
    runner: InsightRunnerDep,
    insight_type: InsightType = Query("monthly", alias="type"),
) -> InsightRunResponse:
    await runner.generate_for_user(user_id, insight_type)
    return InsightRunResponse(generated=1, insight_type=insight_type)
