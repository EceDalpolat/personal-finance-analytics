"""FastAPI dependency wiring. App-lifetime singletons (db pool, http client)
live on app.state; per-request services/repos compose them."""

from typing import Annotated

import asyncpg
import httpx
from fastapi import Depends, Request

from .config import Settings, get_settings
from .repositories.finance_repo import FinanceRepository
from .services.ai_engine_client import AIEngineClient
from .services.finance_service import FinanceService
from .services.superset_service import SupersetService


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


def get_http(request: Request) -> httpx.AsyncClient:
    return request.app.state.http


PoolDep = Annotated[asyncpg.Pool, Depends(get_pool)]
HttpDep = Annotated[httpx.AsyncClient, Depends(get_http)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_finance_service(pool: PoolDep) -> FinanceService:
    return FinanceService(FinanceRepository(pool))


def get_ai_engine_client(http: HttpDep, settings: SettingsDep) -> AIEngineClient:
    return AIEngineClient(http, settings.ai_engine_url)


def get_superset_service(http: HttpDep, settings: SettingsDep) -> SupersetService:
    return SupersetService(
        http,
        base_url=settings.superset_url,
        admin_user=settings.superset_admin_user,
        admin_password=settings.superset_admin_password,
        guest_username=settings.superset_guest_username,
    )


FinanceServiceDep = Annotated[FinanceService, Depends(get_finance_service)]
AIEngineClientDep = Annotated[AIEngineClient, Depends(get_ai_engine_client)]
SupersetServiceDep = Annotated[SupersetService, Depends(get_superset_service)]
