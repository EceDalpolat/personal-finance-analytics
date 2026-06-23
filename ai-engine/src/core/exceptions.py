"""Typed exception hierarchy for ai-engine. Never raise a bare Exception."""


class AIEngineError(Exception):
    """Base class for all ai-engine domain errors."""


class ContextNotFoundError(AIEngineError):
    """No mart_ai_context row exists for the requested user."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f"No AI context found for user_id={user_id}")


class ClaudeAPIError(AIEngineError):
    """Claude API returned an error (non-rate-limit)."""


class ClaudeRateLimitError(ClaudeAPIError):
    """Claude API rate limit hit (HTTP 429)."""


class InsightGenerationError(AIEngineError):
    """Claude responded but the output could not be parsed/validated."""
