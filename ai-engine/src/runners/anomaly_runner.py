"""Anomaly runner — scheduled (weekly). Delegates to InsightRunner with the
'anomaly' insight type."""

from .insight_runner import InsightRunner


class AnomalyRunner:
    def __init__(self, insight_runner: InsightRunner) -> None:
        self._runner = insight_runner

    async def run(self) -> int:
        return await self._runner.run_all("anomaly")
