"""api FastAPI app. Public-facing service: finance mart endpoints, Superset
guest-token minting, and a chat proxy to ai-engine."""

from contextlib import asynccontextmanager

import asyncpg
import httpx
from fastapi import FastAPI

from .config import get_settings
from .core.logging import configure_logging, get_logger
from .core.middleware import RequestContextMiddleware, register_exception_handlers
from .core.tracing import configure_tracing, instrument_app
from .routers import chat, finance, health, superset


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings.service_name, settings.otel_exporter_otlp_endpoint)
    log = get_logger()

    app.state.pool = await asyncpg.create_pool(dsn=settings.analytics_dsn, min_size=1, max_size=5)
    app.state.http = httpx.AsyncClient(timeout=settings.ai_engine_timeout_seconds)
    log.info("api_started", ai_engine_url=settings.ai_engine_url)
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="api", version="0.1.0", lifespan=lifespan)
    instrument_app(app)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(finance.router)
    app.include_router(chat.router)
    app.include_router(superset.router)
    return app


app = create_app()
