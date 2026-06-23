"""Turns a mart_ai_context row into a rendered prompt. Prompts live in
src/prompts/*.j2 — never hardcoded here."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

SYSTEM_PROMPT = (
    "You are a personal finance assistant. You interpret a single user's own "
    "financial data and explain it in clear, friendly, non-judgmental language. "
    "Never invent numbers that are not in the provided context."
)

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class ContextBuilder:
    def __init__(self) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(_PROMPTS_DIR)),
            autoescape=select_autoescape(enabled_extensions=()),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _render(self, template: str, **kwargs) -> str:
        return self._env.get_template(template).render(**kwargs)

    def monthly_insight(self, ctx: dict) -> str:
        return self._render("monthly_insight.j2", ctx=ctx)

    def anomaly(self, ctx: dict) -> str:
        return self._render("anomaly_detection.j2", ctx=ctx)

    def budget_advice(self, ctx: dict) -> str:
        return self._render("budget_advice.j2", ctx=ctx)

    def chat(self, ctx: dict, question: str) -> str:
        return self._render("chat_response.j2", ctx=ctx, question=question)
