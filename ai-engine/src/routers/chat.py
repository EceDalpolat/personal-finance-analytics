"""Chat endpoint: answers a user's natural-language question using their own
mart_ai_context. This is what api/ proxies to."""

from fastapi import APIRouter

from ..dependencies import BuilderDep, ClaudeDep, ContextRepoDep
from ..schemas.chat import ChatRequest, ChatResponse
from ..services.context_builder import SYSTEM_PROMPT

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    context_repo: ContextRepoDep,
    builder: BuilderDep,
    claude: ClaudeDep,
) -> ChatResponse:
    ctx = await context_repo.get_user_context(req.user_id)
    prompt = builder.chat(ctx, req.question)
    answer = await claude.generate_text(system=SYSTEM_PROMPT, prompt=prompt)
    return ChatResponse(user_id=req.user_id, question=req.question, answer=answer, model=claude.model)
