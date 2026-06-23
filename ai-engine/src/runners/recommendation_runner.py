"""Recommendation runner — scheduled (monthly). Delegates to InsightRunner with
the 'recommendation' insight type (budget advice)."""

from .insight_runner import InsightRunner


class RecommendationRunner:
    def __init__(self, insight_runner: InsightRunner) -> None:
        self._runner = insight_runner

    async def run(self) -> int:
        return await self._runner.run_all("recommendation")
