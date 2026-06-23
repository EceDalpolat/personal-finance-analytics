"""Insight schemas. GeneratedInsight is what Claude must return (structured
output); StoredInsight mirrors the ai.insights row."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

InsightType = Literal["monthly", "anomaly", "recommendation"]


class GeneratedInsight(BaseModel):
    """The structured shape Claude returns for a single insight."""

    title: str = Field(..., description="Short headline, max ~80 chars")
    body: str = Field(..., description="2-4 sentence natural-language insight")


# JSON Schema passed to the Claude API via output_config.format. Kept in sync
# with GeneratedInsight by hand (strict structured-output rules).
GENERATED_INSIGHT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["title", "body"],
    "additionalProperties": False,
}


class StoredInsight(BaseModel):
    insight_id: int
    user_id: int
    insight_type: InsightType
    period_month: date | None
    title: str
    body: str
    model: str
    created_at: datetime


class InsightRunResponse(BaseModel):
    """Returned by the insight trigger endpoint."""

    generated: int
    insight_type: InsightType
