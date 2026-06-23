"""Superset guest-token request/response schemas."""

from pydantic import BaseModel, Field


class GuestTokenRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    dashboard_id: str = Field(..., min_length=1)


class GuestTokenResponse(BaseModel):
    user_id: int
    dashboard_id: str
    token: str
