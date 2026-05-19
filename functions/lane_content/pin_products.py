"""
Pinterest Pin Generator — drives traffic from Pinterest to Etsy/Gumroad listings.

Strategy: 5 pins per run, spread across 3 themed boards.
Each pin has unique copy written by Claude + a Canva-style image URL
(uses a free image generation proxy or a stock photo from Unsplash).

Run daily: python run.py content:pin
"""
import sys
import json
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.gumroad_client import get_products
from shared.pinterest_client import get_or_create_board, create_pin
from shared.db import db_session, log_run
from sqlalchemy import text

BOARDS = [
    "AI Tools for Entrepreneurs",
    "Productivity Templates & Prompts",
    "Solopreneur Resources",
]

# Unsplash source gives a random relevant image for free
UNSPLASH_URL = "https://source.unsplash.com/800x1200/?{query}"

PIN_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "title": {"type": "string", "maxLength": 100, "description": "Compelling, curiosity-driven pin title"},
        "description": {"type": "string", "maxLength": 500, "description": "Pinterest description: lead with the transformation/outcome, list 3 benefits, end with CTA. Use line breaks."},
        "image_query": {"type": "string", "description": "2-3 word Unsplash photo query that fits a productivity/business aesthetic"},
        "board_name": {"type": "string", "description": "Which board from the list to pin to"}
    },
    "required": ["title", "description", "image_query", "board_name"]
})


def already_pinned_today(product_id: str, session) -> bool:
    row = session.execute(
        text("""
            SELECT 1 FROM run_log
            WHERE lane='content' AND action='pinterest_pin'
            AND payload->>'product_id' = :pid
            AND created_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
        """),
        {"pid": product_id},
    ).fetchone()
    return row is not None


def run(pins_per_run: int = 5):
    products = get_products()
    published = [p for p in products if p.get("published")]
    if not published:
        print("[pin] No published products to pin.")
        return

    board_ids = {name: get_or_create_board(name) for name in BOARDS}
    pinned = 0

    with db_session() as session:
        for product in published:
            if pinned >= pins_per_run:
                break
            if already_pinned_today(product["id"], session):
                continue

            product_url = product.get("short_url") or product.get("url", "")

            pin_data = orchestrate(
                lane="content",
                task="Write a high-converting Pinterest pin for this digital product.",
                context={
                    "product_name": product.get("name"),
                    "product_url": product_url,
                    "price_usd": float(product.get("price", 0)) / 100,
                    "available_boards": BOARDS,
                    "goal": "Drive clicks from Pinterest to the product page. Speak to the transformation — what can the buyer DO after they have this?",
                },
                response_schema=PIN_SCHEMA,
                use_opus=False,
            )

            board_id = board_ids.get(pin_data["board_name"], list(board_ids.values())[0])
            image_url = UNSPLASH_URL.format(query=pin_data["image_query"].replace(" ", ","))

            pin = create_pin(
                board_id=board_id,
                title=pin_data["title"],
                description=pin_data["description"],
                link=product_url,
                image_url=image_url,
            )

            log_run(
                session=session,
                lane="content",
                action="pinterest_pin",
                payload={"product_id": product["id"], "product_name": product.get("name")},
                result={"pin_id": pin.get("id"), "board": pin_data["board_name"]},
                success=True,
            )
            print(f"[pin] Pinned '{pin_data['title']}' to '{pin_data['board_name']}'")
            pinned += 1

    print(f"[pin] Done — {pinned} pins created.")


if __name__ == "__main__":
    run()
