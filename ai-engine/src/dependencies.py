"""FastAPI dependency wiring. App-lifetime singletons (db pool, Claude service,
context builder) live on app.state; per-request repos/runners compose them."""

from typing import Annotated

import asyncpg
from fastapi import Depends, Request

from .repositories.context_repo import ContextRepository
from .repositories.insight_repo import InsightRepository
from .runners.insight_runner import InsightRunner
from .services.claude_service import ClaudeService
from .services.context_builder import ContextBuilder


def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool


def get_claude(request: Request) -> ClaudeService:
    return request.app.state.claude


def get_builder(request: Request) -> ContextBuilder:
    return request.app.state.builder


PoolDep = Annotated[asyncpg.Pool, Depends(get_pool)]
ClaudeDep = Annotated[ClaudeService, Depends(get_claude)]
BuilderDep = Annotated[ContextBuilder, Depends(get_builder)]


def get_context_repo(pool: PoolDep) -> ContextRepository:
    return ContextRepository(pool)


def get_insight_repo(pool: PoolDep) -> InsightRepository:
    return InsightRepository(pool)


ContextRepoDep = Annotated[ContextRepository, Depends(get_context_repo)]
InsightRepoDep = Annotated[InsightRepository, Depends(get_insight_repo)]


def get_insight_runner(
    context_repo: ContextRepoDep,
    insight_repo: InsightRepoDep,
    builder: BuilderDep,
    claude: ClaudeDep,
) -> InsightRunner:
    return InsightRunner(context_repo, insight_repo, builder, claude)


InsightRunnerDep = Annotated[InsightRunner, Depends(get_insight_runner)]
