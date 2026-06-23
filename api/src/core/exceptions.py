"""Typed exception hierarchy for api. Never raise a bare Exception."""


class ApiError(Exception):
    """Base class for all api domain errors."""


class UserNotFoundError(ApiError):
    """No finance mart rows exist for the requested user."""

    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        super().__init__(f"No financial data found for user_id={user_id}")


class AIEngineError(ApiError):
    """The downstream ai-engine call failed or returned an error."""


class AIEngineRateLimitError(AIEngineError):
    """ai-engine (or Claude behind it) returned a rate-limit (HTTP 429)."""


class SupersetError(ApiError):
    """A Superset API call (login or guest-token mint) failed."""
