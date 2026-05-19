"""
Publish a generated product PDF to Etsy as a digital download listing.
Called from generate_product.py after the PDF is built, or standalone.

Usage: python run.py content:etsy --product-id <gumroad_product_id>
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.etsy_client import get_shop_id, create_draft_listing, upload_listing_file, publish_listing
from shared.gumroad_client import get_products

ETSY_TAGS_SCHEMA = """{
  "type": "object",
  "properties": {
    "tags": {
      "type": "array",
      "maxItems": 13,
      "items": {"type": "string", "maxLength": 20},
      "description": "SEO tags for Etsy. Use single words or two-word phrases. No special chars."
    },
    "etsy_title": {
      "type": "string",
      "maxLength": 140,
      "description": "Etsy listing title — keyword-rich, benefit-first, no all-caps"
    },
    "etsy_description": {
      "type": "string",
      "description": "Etsy listing description. Lead with the pain point, list what's included, end with social proof framing. 200-400 words. Plain text only."
    }
  },
  "required": ["tags", "etsy_title", "etsy_description"]
}"""


def publish_product_to_etsy(product: dict, pdf_path: str) -> dict:
    """Given a product dict (from Gumroad) and local pdf_path, list it on Etsy."""
    name = product.get("name", "AI Prompt Pack")
    price = float(product.get("price", 2700)) / 100

    # Ask Claude to write Etsy-optimised copy and tags
    etsy_data = orchestrate(
        lane="content",
        task="Write SEO-optimised Etsy listing copy and tags for this digital product.",
        context={"product_name": name, "price_usd": price},
        response_schema=ETSY_TAGS_SCHEMA,
        use_opus=False,
    )

    shop_id = get_shop_id()
    listing = create_draft_listing(
        shop_id=shop_id,
        title=etsy_data["etsy_title"],
        description=etsy_data["etsy_description"],
        price_usd=price,
        tags=etsy_data["tags"],
        digital=True,
    )
    listing_id = listing["listing_id"]
    upload_listing_file(shop_id, listing_id, pdf_path)
    published = publish_listing(shop_id, listing_id)
    print(f"[etsy] Live: listing {listing_id} — {etsy_data['etsy_title']}")
    return published


def run():
    """Standalone: fetch latest Gumroad product that isn't on Etsy yet and list it."""
    import os
    from shared.db import db_session
    from sqlalchemy import text

    products = get_products()
    with db_session() as session:
        listed_ids = {
            row[0]
            for row in session.execute(
                text("SELECT metadata->>'gumroad_id' FROM kv_store WHERE lane='content' AND key LIKE 'etsy_listed_%'")
            ).fetchall()
        }

    unlisted = [p for p in products if p["id"] not in listed_ids and p.get("published")]
    if not unlisted:
        print("[etsy] No unlisted products found.")
        return

    product = unlisted[0]
    print(f"[etsy] Listing: {product['name']}")

    # Re-generate PDF locally (we don't store the file on Gumroad)
    from functions.lane_content.generate_product import orchestrate as orch, PRODUCT_SCHEMA, pick_niche
    from shared.pdf_builder import build_prompt_pack
    from datetime import datetime, timezone

    context = {
        "niche": product["name"],
        "goal": "Recreate this product's content for PDF rendering.",
        "date": datetime.now(timezone.utc).isoformat(),
    }
    product_data = orch(
        lane="content",
        task="Recreate the full product content matching the given title.",
        context=context,
        response_schema=PRODUCT_SCHEMA,
        use_opus=False,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "product.pdf")
        build_prompt_pack(pdf_path, product_data)
        result = publish_product_to_etsy(product, pdf_path)

    # Mark as listed
    with db_session() as session:
        session.execute(
            text("""
                INSERT INTO kv_store (lane, key, value, updated_at)
                VALUES ('content', :key, :val::jsonb, NOW())
                ON CONFLICT (lane, key) DO NOTHING
            """),
            {"key": f"etsy_listed_{product['id']}", "val": f'{{"gumroad_id": "{product["id"]}", "etsy_listing_id": {result.get("listing_id")}}}'},
        )
    return result


if __name__ == "__main__":
    run()
