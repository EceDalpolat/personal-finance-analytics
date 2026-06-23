"""Superset router — mints per-user guest tokens for embedded dashboards."""

from fastapi import APIRouter

from ..dependencies import SupersetServiceDep
from ..schemas.superset import GuestTokenRequest, GuestTokenResponse

router = APIRouter(prefix="/superset", tags=["superset"])


@router.post("/guest-token", response_model=GuestTokenResponse)
async def guest_token(req: GuestTokenRequest, superset: SupersetServiceDep) -> GuestTokenResponse:
    token = await superset.mint_guest_token(req.user_id, req.dashboard_id)
    return GuestTokenResponse(user_id=req.user_id, dashboard_id=req.dashboard_id, token=token)
