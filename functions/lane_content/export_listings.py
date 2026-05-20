"""
Export ready-to-paste listing copy for all products.
Writes brand/listings.txt -- one block per product with everything needed
to manually post on Gumroad, Ko-fi, Payhip, or any platform.

Run: python run.py content:export
"""
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"
OUTPUT_DIR = Path(__file__).resolve().parents[2] / "brand"


def run():
    json_files = sorted(PRODUCTS_DIR.glob("*.json"))
    if not json_files:
        print("[export] No products found. Run content:generate first.")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "listings.txt"

    lines = []
    lines.append("HONE PRODUCT LISTINGS")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Products: {len(json_files)}")
    lines.append("=" * 60)
    lines.append("")

    for json_path in json_files:
        with open(json_path, encoding="utf-8") as f:
            p = json.load(f)

        slug = p.get("slug", json_path.stem)
        price = p.get("price_cents", 0) / 100
        prompt_count = sum(len(s.get("prompts", [])) for s in p.get("sections", []))
        pdf_file = f"products/{slug}.pdf"

        lines.append(f"PRODUCT: {slug}")
        lines.append("-" * 60)
        lines.append(f"PDF FILE : {pdf_file}")
        lines.append(f"PRICE    : ${price:.2f}")
        lines.append(f"PROMPTS  : {prompt_count} prompts across {len(p.get('sections', []))} sections")
        lines.append("")
        lines.append(f"TITLE (store listing name):")
        lines.append(f"  {p.get('store_name', '')}")
        lines.append("")
        lines.append(f"DESCRIPTION (paste into product description):")
        lines.append(p.get("store_description", ""))
        lines.append("")
        lines.append(f"TAGS (for Etsy -- max 13, each under 20 chars):")
        lines.append(", ".join(p.get("etsy_tags", [])))
        lines.append("")
        lines.append(f"SHORT DESCRIPTION (for social / pin captions):")
        lines.append(p.get("intro", "")[:280])
        lines.append("")
        lines.append("=" * 60)
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[export] Listings written to: {output_path}")
    print(f"[export] {len(json_files)} products")
    print()
    print("  HOW TO LIST ON GUMROAD MANUALLY:")
    print("  1. gumroad.com -> New Product -> Digital")
    print("  2. Paste TITLE into product name")
    print("  3. Paste DESCRIPTION into the description field")
    print("  4. Set price to the listed amount")
    print("  5. Upload the PDF file")
    print("  6. Publish")
    print()


if __name__ == "__main__":
    run()
