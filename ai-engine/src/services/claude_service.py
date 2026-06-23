"""Anthropic SDK wrapper. The only place that talks to Claude. Owns the model
choice, token limits, error mapping, and tracing. Model is claude-sonnet-4-6
(pinned by CLAUDE.md)."""

import json
import time

import anthropic
import structlog

from ..core.exceptions import ClaudeAPIError, ClaudeRateLimitError, InsightGenerationError
from ..core.tracing import get_tracer

log = structlog.get_logger()
_tracer = get_tracer("ai-engine.claude")


class ClaudeService:
    def __init__(self, api_key: str, model: str, max_tokens: int, effort: str, use_thinking: bool) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens
        self._effort = effort
        self._use_thinking = use_thinking

    @property
    def model(self) -> str:
        return self._model

    async def generate_structured(self, *, system: str, prompt: str, schema: dict) -> dict:
        """Call Claude with a JSON-schema-constrained response; return parsed dict."""
        with _tracer.start_as_current_span("claude.generate_structured") as span:
            span.set_attribute("ai.model", self._model)
            try:
                resp = await self._client.messages.create(
                    model=self._model,
                    max_tokens=self._max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": prompt}],
                    output_config={
                        "effort": self._effort,
                        "format": {"type": "json_schema", "schema": schema},
                    },
                )
            except anthropic.RateLimitError as exc:
                raise ClaudeRateLimitError(str(exc)) from exc
            except anthropic.APIStatusError as exc:
                raise ClaudeAPIError(f"Claude API error {exc.status_code}: {exc.message}") from exc

            self._record_usage(span, resp)
            text = next((b.text for b in resp.content if b.type == "text"), None)
            if not text:
                raise InsightGenerationError("Claude returned no text content")
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise InsightGenerationError(f"Claude output was not valid JSON: {exc}") from exc

    async def generate_text(self, *, system: str, prompt: str) -> str:
        """Free-form text answer (chat). Uses adaptive thinking when enabled."""
        with _tracer.start_as_current_span("claude.generate_text") as span:
            span.set_attribute("ai.model", self._model)
            kwargs: dict = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
                "output_config": {"effort": self._effort},
            }
            if self._use_thinking:
                kwargs["thinking"] = {"type": "adaptive"}
            try:
                resp = await self._client.messages.create(**kwargs)
            except anthropic.RateLimitError as exc:
                raise ClaudeRateLimitError(str(exc)) from exc
            except anthropic.APIStatusError as exc:
                raise ClaudeAPIError(f"Claude API error {exc.status_code}: {exc.message}") from exc

            self._record_usage(span, resp)
            return "".join(b.text for b in resp.content if b.type == "text").strip()

    @staticmethod
    def _record_usage(span, resp) -> None:
        usage = getattr(resp, "usage", None)
        if usage:
            span.set_attribute("ai.input_tokens", usage.input_tokens)
            span.set_attribute("ai.output_tokens", usage.output_tokens)
        span.set_attribute("ai.stop_reason", resp.stop_reason or "")
