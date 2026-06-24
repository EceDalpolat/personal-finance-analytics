"""ai-engine FastAPI app. Internal AI service: chat + insight generation."""

from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI

from .config import get_settings
from .core.logging import configure_logging, get_logger
from .core.middleware import RequestContextMiddleware, register_exception_handlers
from .core.tracing import configure_tracing, instrument_app
from .routers import chat, health, insights
from .services.claude_service import ClaudeService
from .services.context_builder import ContextBuilder


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    configure_tracing(settings.service_name, settings.otel_exporter_otlp_endpoint)
    log = get_logger()

    app.state.pool = await asyncpg.create_pool(dsn=settings.analytics_dsn, min_size=1, max_size=5)
    app.state.claude = ClaudeService(
        api_key=settings.anthropic_api_key,
        model=settings.ai_model_id,
        max_tokens=settings.ai_max_tokens,
        effort=settings.ai_effort,
        use_thinking=settings.ai_use_thinking,
    )
    app.state.builder = ContextBuilder()
    log.info("ai_engine_started", model=settings.ai_model_id)
    try:
        yield
    finally:
        await app.state.pool.close()


def create_app() -> FastAPI:
    app = FastAPI(title="ai-engine", version="0.1.0", lifespan=lifespan)
    instrument_app(app)
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(insights.router)
    app.include_router(chat.router)
    return app


app = create_app()
