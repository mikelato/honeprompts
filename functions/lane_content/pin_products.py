"""
Pinterest Pin Content Generator.

Since Pinterest API requires a website before approval, this generates
ready-to-post pin content and exports a weekly schedule CSV that you
paste into Pinterest's free native scheduler (pinterest.com/scheduler).

Run: python run.py content:pin
Output: brand/pinterest_schedule.csv — upload to Pinterest
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.gumroad_client import get_products

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
        "board_name": {
            "type": "string",
            "description": "Which board this pin belongs on"
        },
        "image_headline": {
            "type": "string",
            "maxLength": 60,
            "description": "Bold text to overlay on the pin image — the biggest hook, very short"
        },
        "image_subtext": {
            "type": "string",
            "maxLength": 80,
            "description": "Secondary text for pin image — what they get or a specific number"
        }
    },
    "required": ["title", "description", "board_name", "image_headline", "image_subtext"]
})

# Pinterest's scheduler accepts: Title, Description, Link, Board, Publish Date
CSV_HEADERS = ["Title", "Description", "Link", "Board", "Publish Date", "Image Headline", "Image Subtext"]


def generate_pins_for_product(product: dict, count: int = 3) -> list[dict]:
    pins = []
    for i in range(count):
        pin = orchestrate(
            lane="content",
            task=f"Write Pinterest pin #{i+1} of {count} for this product. Each pin must have a different angle and hook.",
            context={
                "product_name": product.get("name"),
                "product_url": product.get("short_url") or product.get("url", ""),
                "price_usd": float(product.get("price", 0)) / 100,
                "brand": BRAND_NAME,
                "available_boards": BOARDS,
                "angle_number": i + 1,
                "angle_hints": [
                    "Focus on time saved / efficiency angle",
                    "Focus on specific results / outcomes angle",
                    "Focus on the frustration they're escaping angle",
                ][i % 3],
            },
            response_schema=PIN_SCHEMA,
            use_opus=False,
        )
        pin["product_url"] = product.get("short_url") or product.get("url", "")
        pins.append(pin)
    return pins


def run(pins_per_product: int = 3):
    products = get_products()
    published = [p for p in products if p.get("published")]

    if not published:
        print("[pin] No published products. Run content:generate first.")
        return

    output_path = Path(__file__).resolve().parents[2] / "brand" / "pinterest_schedule.csv"
    output_path.parent.mkdir(exist_ok=True)

    all_rows = []
    # Spread pins across the next 7 days, 2 per day at 9am and 7pm UTC
    slot_times = []
    now = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
    for day in range(7):
        day_base = now + timedelta(days=day)
        slot_times.append(day_base)
        slot_times.append(day_base.replace(hour=19))

    slot_index = 0
    for product in published:
        print(f"[pin] Generating pins for: {product['name']}")
        pins = generate_pins_for_product(product, count=pins_per_product)
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

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADERS)
        writer.writerows(all_rows)

    print(f"\n✓ Pinterest schedule exported: {output_path}")
    print(f"  {len(all_rows)} pins across {min(7, len(all_rows))} days")
    print()
    print("  NEXT STEPS:")
    print("  1. Open brand/pinterest_schedule.csv")
    print("  2. For each row: create a Canva pin using the Image Headline + Image Subtext")
    print("     (Use the 1000x1500 template from brand/copy.md)")
    print("  3. Go to pinterest.com → Create → Create Pin → use the Title, Description, Link, Board")
    print("  4. Or upload to Tailwind (tailwindapp.com) for bulk scheduling — free tier available")
    print()


if __name__ == "__main__":
    run()
