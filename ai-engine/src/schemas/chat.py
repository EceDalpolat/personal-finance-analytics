"""Chat request/response schemas (the contract api/ proxies to)."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: int = Field(..., ge=1)
    question: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    user_id: int
    question: str
    answer: str
    model: str
