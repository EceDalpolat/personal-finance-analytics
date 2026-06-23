"""Chat router — proxies the user's question to ai-engine. api never calls
Claude directly (CLAUDE.md)."""

from fastapi import APIRouter

from ..dependencies import AIEngineClientDep
from ..schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, ai_engine: AIEngineClientDep) -> ChatResponse:
    return await ai_engine.chat(req.user_id, req.question)
