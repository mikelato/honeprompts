"""
Pinterest Pin Content Generator.

Generates ready-to-schedule pin copy for every product in the local catalog.
Exports a CSV for Pinterest's native scheduler (pinterest.com/scheduler) or Tailwind.

Run: python run.py content:pin
Output: brand/pinterest_schedule.csv
"""
import csv
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.db import db_session, log_run
from sqlalchemy import text

PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"
BRAND_NAME = "Hone"

BOARDS = [
    "AI Prompts for Entrepreneurs",
    "Productivity Templates & Tools",
    "Solopreneur Resources",
]

PIN_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "maxLength": 100,
            "description": "Hook-driven pin title. Lead with the transformation or a curiosity gap. No clickbait."
        },
        "description": {
            "type": "string",
            "maxLength": 500,
            "description": (
                "Pinterest description. Line 1: the pain. Line 2: the outcome. "
                "Lines 3-5: 3 specific things included. Final line: CTA to get it. "
                "Use line breaks between each. Natural voice, no hashtag spam."
            )
        },
        "board_name": {"type": "string", "description": "Which board this pin belongs on"},
        "image_headline": {
            "type": "string",
            "maxLength": 60,
            "description": "Bold text for pin image overlay -- the biggest hook, very short"
        },
        "image_subtext": {
            "type": "string",
            "maxLength": 80,
            "description": "Secondary image text -- what they get or a specific number"
        }
    },
    "required": ["title", "description", "board_name", "image_headline", "image_subtext"]
})

CSV_HEADERS = ["Title", "Description", "Link", "Board", "Publish Date", "Image Headline", "Image Subtext"]

ANGLE_HINTS = [
    "Focus on time saved / efficiency angle",
    "Focus on specific results / outcomes angle",
    "Focus on the frustration they're escaping angle",
]


def _get_product_url(slug: str) -> str:
    """Return the Lemon Squeezy buy URL for a slug, or empty string."""
    try:
        with db_session() as session:
            row = session.execute(
                text("SELECT value FROM kv_store WHERE lane='content' AND key = :key"),
                {"key": f"lemon_product_{slug}"},
            ).fetchone()
        if row:
            return row[0].get("buy_now_url", "")
    except Exception:
        pass
    return ""


def generate_pins_for_product(product_data: dict, url: str, count: int = 3) -> list[dict]:
    pins = []
    for i in range(count):
        pin = orchestrate(
            lane="content",
            task=f"Write Pinterest pin #{i+1} of {count} for this product. Each pin must have a different angle and hook.",
            context={
                "product_name": product_data.get("store_name", product_data.get("title")),
                "product_url": url,
                "price_usd": product_data.get("price_cents", 0) / 100,
                "brand": BRAND_NAME,
                "available_boards": BOARDS,
                "angle_hints": ANGLE_HINTS[i % 3],
                "intro": product_data.get("intro", ""),
            },
            response_schema=PIN_SCHEMA,
            use_opus=False,
        )
        pin["product_url"] = url
        pins.append(pin)
    return pins


def run(pins_per_product: int = 3):
    json_files = sorted(f for f in PRODUCTS_DIR.glob("*.json") if f.name != "urls.json")
    if not json_files:
        print("[pin] No products found in products/. Run content:generate first.")
        return

    output_path = Path(__file__).resolve().parents[2] / "brand" / "pinterest_schedule.csv"
    output_path.parent.mkdir(exist_ok=True)

    # Spread pins across 7 days at 9am and 7pm UTC
    now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    slot_times = []
    for day in range(7):
        base = now + timedelta(days=day)
        slot_times.append(base)
        slot_times.append(base.replace(hour=19))

    all_rows = []
    slot_index = 0

    for json_path in json_files:
        slug = json_path.stem
        with open(json_path, encoding="utf-8") as f:
            product_data = json.load(f)

        url = _get_product_url(slug)
        print(f"[pin] Generating {pins_per_product} pins for: {slug}")
        pins = generate_pins_for_product(product_data, url, count=pins_per_product)

        for pin in pins:
            if slot_index >= len(slot_times):
                break
            publish_at = slot_times[slot_index].strftime("%Y-%m-%dT%H:%M:%S")
            all_rows.append([
                pin["title"],
                pin["description"],
                pin["product_url"],
                pin["board_name"],
                publish_at,
                pin["image_headline"],
                pin["image_subtext"],
            ])
            slot_index += 1

        with db_session() as session:
            log_run(
                session=session,
                lane="content",
                action="pinterest_pin",
                payload={"slug": slug, "pins_generated": len(pins)},
                result={"rows_added": len(pins)},
                success=True,
            )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        writer.writerows(all_rows)

    print(f"\n  Pinterest schedule exported: {output_path}")
    print(f"  {len(all_rows)} pins across {min(7, (len(all_rows) + 1) // 2)} days")
    print()
    print("  NEXT STEPS:")
    print("  1. Create a Canva pin image for each row (1000x1500px)")
    print("     Use the Image Headline as bold overlay text")
    print("  2. Upload to pinterest.com/scheduler or Tailwind (free tier)")
    print()


if __name__ == "__main__":
    run()
