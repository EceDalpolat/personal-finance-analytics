"""Thin client over the internal ai-engine service. api never calls Claude
directly — every chat request is proxied here (CLAUDE.md AI engine rule)."""

import httpx
import structlog

from ..core.exceptions import AIEngineError, AIEngineRateLimitError
from ..schemas.chat import ChatResponse

log = structlog.get_logger()


class AIEngineClient:
    def __init__(self, http: httpx.AsyncClient, base_url: str) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def chat(self, user_id: int, question: str) -> ChatResponse:
        try:
            resp = await self._http.post(
                f"{self._base_url}/chat",
                json={"user_id": user_id, "question": question},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise AIEngineRateLimitError("ai-engine rate limited") from exc
            raise AIEngineError(
                f"ai-engine returned {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIEngineError(f"ai-engine unreachable: {exc}") from exc
        log.info("chat_proxied", user_id=user_id)
        return ChatResponse.model_validate(resp.json())
