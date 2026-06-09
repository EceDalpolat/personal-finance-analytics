# ai-engine — prompt design, runner logic, context building

## Rules
- Prompts live in `src/prompts/*.j2` — never hardcoded in Python
- `context_builder.py` converts `mart_ai_context` rows into prompt context
- Claude model: `claude-sonnet-4-6` (pinned)
- Token limits + retry handled only in `claude_service.py`

## Runners
- `insight_runner` — triggered after `dbt build`
- `anomaly_runner` — scheduled, weekly
- `recommendation_runner` — scheduled, monthly
