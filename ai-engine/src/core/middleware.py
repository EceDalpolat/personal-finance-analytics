"""Request middleware: generate a request_id, time the response, bind logging
context, and convert domain errors into clean JSON responses."""

import time
import uuid

import structlog
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .exceptions import (
    AIEngineError,
    ClaudeRateLimitError,
    ContextNotFoundError,
)

log = structlog.get_logger()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id, path=request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled_error")
            raise
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-request-id"] = request_id
        log.info("request", method=request.method, status=response.status_code, duration_ms=duration_ms)
        return response


def register_exception_handlers(app) -> None:
    @app.exception_handler(ContextNotFoundError)
    async def _not_found(_: Request, exc: ContextNotFoundError):
        return JSONResponse(status_code=404, content={"error": "context_not_found", "detail": str(exc)})

    @app.exception_handler(ClaudeRateLimitError)
    async def _rate_limited(_: Request, exc: ClaudeRateLimitError):
        return JSONResponse(status_code=429, content={"error": "claude_rate_limited", "detail": str(exc)})

    @app.exception_handler(AIEngineError)
    async def _domain_error(_: Request, exc: AIEngineError):
        return JSONResponse(status_code=502, content={"error": "ai_engine_error", "detail": str(exc)})
