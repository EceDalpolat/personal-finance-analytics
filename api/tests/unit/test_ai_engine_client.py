"""AIEngineClient unit test — httpx MockTransport. Verifies the chat proxy
maps a 429 from ai-engine to AIEngineRateLimitError and parses a success body."""

import httpx
import pytest

from src.core.exceptions import AIEngineError, AIEngineRateLimitError
from src.services.ai_engine_client import AIEngineClient


async def test_chat_returns_parsed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"user_id": 1, "question": "how am I doing?", "answer": "Great.", "model": "claude-sonnet-4-6"},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        resp = await AIEngineClient(http, "http://ai-engine:8000").chat(1, "how am I doing?")

    assert resp.answer == "Great."
    assert resp.model == "claude-sonnet-4-6"


async def test_chat_maps_429_to_rate_limit_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": "rate_limited"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AIEngineClient(http, "http://ai-engine:8000")
        with pytest.raises(AIEngineRateLimitError):
            await client.chat(1, "q")


async def test_chat_maps_5xx_to_ai_engine_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = AIEngineClient(http, "http://ai-engine:8000")
        with pytest.raises(AIEngineError):
            await client.chat(1, "q")
