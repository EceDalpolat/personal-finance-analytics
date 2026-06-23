"""Insight runner: read a user's mart_ai_context, render a prompt, ask Claude
for a structured insight, and store it in ai.insights. Triggered after dbt build."""

import structlog

from ..repositories.context_repo import ContextRepository
from ..repositories.insight_repo import InsightRepository
from ..schemas.insight import GENERATED_INSIGHT_SCHEMA, GeneratedInsight, InsightType
from ..services.claude_service import ClaudeService
from ..services.context_builder import SYSTEM_PROMPT, ContextBuilder

log = structlog.get_logger()


class InsightRunner:
    def __init__(
        self,
        context_repo: ContextRepository,
        insight_repo: InsightRepository,
        builder: ContextBuilder,
        claude: ClaudeService,
    ) -> None:
        self._context = context_repo
        self._insights = insight_repo
        self._builder = builder
        self._claude = claude

    def _build_prompt(self, ctx: dict, insight_type: InsightType) -> str:
        if insight_type == "monthly":
            return self._builder.monthly_insight(ctx)
        if insight_type == "anomaly":
            return self._builder.anomaly(ctx)
        return self._builder.budget_advice(ctx)  # recommendation

    async def generate_for_user(self, user_id: int, insight_type: InsightType) -> int:
        ctx = await self._context.get_user_context(user_id)
        prompt = self._build_prompt(ctx, insight_type)
        raw = await self._claude.generate_structured(
            system=SYSTEM_PROMPT, prompt=prompt, schema=GENERATED_INSIGHT_SCHEMA
        )
        insight = GeneratedInsight.model_validate(raw)
        insight_id = await self._insights.add_insight(
            user_id=user_id,
            insight_type=insight_type,
            title=insight.title,
            body=insight.body,
            model=self._claude.model,
            period_month=ctx.get("latest_month"),
        )
        log.info("insight_generated", user_id=user_id, insight_type=insight_type, insight_id=insight_id)
        return insight_id

    async def run_all(self, insight_type: InsightType) -> int:
        """Generate one insight of the given type for every user. Returns count."""
        user_ids = await self._context.list_user_ids()
        generated = 0
        for user_id in user_ids:
            try:
                await self.generate_for_user(user_id, insight_type)
                generated += 1
            except Exception:
                log.exception("insight_failed", user_id=user_id, insight_type=insight_type)
        log.info("insight_run_complete", insight_type=insight_type, generated=generated, total=len(user_ids))
        return generated
