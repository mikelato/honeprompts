import anthropic
import os
from typing import Any

_client: anthropic.Anthropic | None = None

ORCHESTRATOR_SYSTEM = """You are the product and content engine for Hone (gethone.co), a brand that sells professional AI prompt packs for founders, freelancers, and solopreneurs.

Brand voice: direct, practical, no hype. Every output should sound like advice from a sharp colleague.
Brand promise: every prompt is complete and ready to paste — zero editing required by the buyer.

Your job is to generate products and content that:
1. Solve a specific, real problem the buyer has today
2. Deliver immediate, tangible value — not theory
3. Sound professional and trustworthy, never salesy
4. Can be listed and sold without further editing

Respond with valid JSON matching the schema the caller specifies."""


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
        max_tokens=8000,
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
    text = text.strip()

    # If response was truncated, attempt to close the JSON
    stop_reason = response.stop_reason
    if stop_reason == "max_tokens":
        # Try to salvage by closing open structures
        for closing in ["]}]}", "]}", "}"]:
            try:
                return json.loads(text + closing)
            except json.JSONDecodeError:
                pass
        raise RuntimeError(
            f"Claude response truncated at max_tokens and could not be repaired. "
            f"Last 100 chars: ...{text[-100:]}"
        )

    return json.loads(text)
