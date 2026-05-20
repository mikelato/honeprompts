"""
Publish generated prompt pack PDFs to Etsy as digital download listings.
Uses local products/*.json + products/*.pdf as the source of truth.

Usage:
    python run.py content:etsy        # list all un-listed products
    python run.py content:etsy <slug> # list a specific product by slug
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.etsy_client import get_shop_id, create_draft_listing, upload_listing_file, publish_listing
from shared.db import db_session, log_run
from sqlalchemy import text

PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"

ETSY_COPY_SCHEMA = """{
  "type": "object",
  "properties": {
    "etsy_title": {
      "type": "string",
      "maxLength": 140,
      "description": "Etsy listing title -- keyword-rich, benefit-first, max 140 chars. No all-caps."
    },
    "etsy_description": {
      "type": "string",
      "description": "Etsy listing description. Lead with the pain point, list what's included (bullet style with dashes), end with a social-proof framing. 200-400 words. Plain text only."
    }
  },
  "required": ["etsy_title", "etsy_description"]
}"""


def publish_product_to_etsy(product_data: dict, pdf_path: str) -> dict:
    """List a single product on Etsy. product_data is the local JSON structure."""
    slug = product_data["slug"]
    name = product_data["store_name"]
    price_usd = product_data["price_cents"] / 100
    tags = product_data.get("etsy_tags", [])[:13]

    etsy_copy = orchestrate(
        lane="content",
        task="Write an Etsy-optimised listing title and description for this digital prompt pack.",
        context={
            "product_name": name,
            "store_description": product_data.get("store_description", ""),
            "price_usd": price_usd,
            "tags": tags,
        },
        response_schema=ETSY_COPY_SCHEMA,
        use_opus=False,
    )

    shop_id = get_shop_id()
    listing = create_draft_listing(
        shop_id=shop_id,
        title=etsy_copy["etsy_title"],
        description=etsy_copy["etsy_description"],
        price_usd=price_usd,
        tags=tags,
        digital=True,
    )
    listing_id = listing["listing_id"]
    upload_listing_file(shop_id, listing_id, pdf_path)
    published = publish_listing(shop_id, listing_id)

    # Record in kv_store so we don't double-list
    with db_session() as session:
        session.execute(
            text("""
                INSERT INTO kv_store (lane, key, value, updated_at)
                VALUES ('content', :key, :val::jsonb, NOW())
                ON CONFLICT (lane, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """),
            {
                "key": f"etsy_listed_{slug}",
                "val": json.dumps({
                    "slug": slug,
                    "listing_id": listing_id,
                    "etsy_title": etsy_copy["etsy_title"],
                }),
            },
        )
        log_run(
            session=session,
            lane="content",
            action="etsy_listing",
            payload={"slug": slug, "listing_id": listing_id},
            result={"etsy_title": etsy_copy["etsy_title"]},
            success=True,
        )

    print(f"[etsy] Listed: {etsy_copy['etsy_title']} (listing {listing_id})")
    return published


def run(target_slug: str | None = None):
    """List all unlisted local products on Etsy, or a specific slug."""
    json_files = sorted(PRODUCTS_DIR.glob("*.json"))
    if not json_files:
        print("[etsy] No products found in products/. Run content:generate first.")
        return

    # Fetch already-listed slugs from kv_store
    with db_session() as session:
        rows = session.execute(
            text("SELECT key FROM kv_store WHERE lane='content' AND key LIKE 'etsy_listed_%'")
        ).fetchall()
    listed_slugs = {row[0].replace("etsy_listed_", "") for row in rows}

    for json_path in json_files:
        slug = json_path.stem
        if target_slug and slug != target_slug:
            continue
        if slug in listed_slugs:
            print(f"[etsy] Already listed: {slug}")
            continue

        pdf_path = PRODUCTS_DIR / f"{slug}.pdf"
        if not pdf_path.exists():
            print(f"[etsy] Missing PDF for {slug}, skipping.")
            continue

        with open(json_path, encoding="utf-8") as f:
            product_data = json.load(f)

        print(f"[etsy] Listing: {slug}")
        try:
            publish_product_to_etsy(product_data, str(pdf_path))
        except Exception as e:
            print(f"[etsy] Failed for {slug}: {e}")


if __name__ == "__main__":
    slug = sys.argv[2] if len(sys.argv) > 2 else None
    run(slug)
