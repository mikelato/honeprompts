import anthropic
import os
from typing import Any

_client: anthropic.Anthropic | None = None

ORCHESTRATOR_SYSTEM = """You are the AI Income Engine orchestrator. Your job is to make decisions that generate real, sustainable income.

You operate income lanes — automated systems that create value and capture revenue:
- Content/Digital Products: Generate sellable digital products (prompt packs, templates, guides)
- Newsletter: Curate and write content that builds audience and affiliate income
- Leads: Identify and qualify business opportunities

For every action you take:
1. Maximize revenue per unit of effort
2. Choose quality over quantity — one excellent product beats ten mediocre ones
3. Target buyers, not browsers — every output should be aimed at someone with a real problem and money to solve it
4. Track everything — every decision and result goes to the database

Respond with valid JSON matching the Action schema the caller specifies."""


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


def orchestrate(
    lane: str,
    task: str,
    context: dict[str, Any],
    response_schema: str,
    use_opus: bool = False,
) -> dict[str, Any]:
    """Single entry point for all Claude API calls. Uses prompt caching on system prompt."""
    import json

    client = get_client()
    model = "claude-opus-4-7" if use_opus else "claude-sonnet-4-6"

    user_content = f"""Lane: {lane}
Task: {task}
Context: {json.dumps(context, indent=2)}

Respond with valid JSON matching this schema:
{response_schema}"""

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": ORCHESTRATOR_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    text = response.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
