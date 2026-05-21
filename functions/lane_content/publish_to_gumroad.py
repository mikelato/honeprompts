"""
Publish all built products to Gumroad and write buy URLs to products/urls.json.

Run: python run.py content:gumroad
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.gumroad_client import create_product, attach_file, publish_product, get_products

PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"
URLS_PATH = PRODUCTS_DIR / "urls.json"
RATE_LIMIT_DELAY = 3  # seconds between Gumroad API calls


def _load_urls() -> dict:
    if URLS_PATH.exists():
        return json.loads(URLS_PATH.read_text(encoding="utf-8"))
    return {}


def _save_urls(urls: dict):
    URLS_PATH.write_text(json.dumps(urls, indent=2), encoding="utf-8")


def run():
    urls = _load_urls()

    # Index existing Gumroad products by name
    existing_by_name = {p["name"]: p for p in get_products()}
    print(f"[gumroad] {len(existing_by_name)} products already on Gumroad")

    product_jsons = sorted(PRODUCTS_DIR.glob("*.json"))
    if not product_jsons:
        print("[gumroad] No product JSON files found — run content:generate first")
        return

    published = 0
    skipped = 0

    for meta_path in product_jsons:
        if meta_path.name == "urls.json":
            continue

        data = json.loads(meta_path.read_text(encoding="utf-8"))
        slug = data.get("slug", meta_path.stem)
        pdf_path = PRODUCTS_DIR / f"{slug}.pdf"

        if not pdf_path.exists():
            print(f"  [skip] {slug} — PDF not found")
            skipped += 1
            continue

        name = data.get("store_name", data.get("title", slug))
        description = data.get("store_description", "")
        price_cents = data.get("price_cents", 2700)

        existing = existing_by_name.get(name)

        if existing:
            product_id = existing["id"]
            short_url = existing.get("short_url", "")
            is_published = existing.get("published", False)

            if is_published and short_url:
                urls[slug] = short_url
                _save_urls(urls)
                print(f"  [skip] {slug} — already live: {short_url}")
                skipped += 1
                continue

            # Exists but unpublished — attach file and publish
            print(f"  [attach] {slug} — attaching PDF to existing product...")
            try:
                attach_file(product_id, str(pdf_path))
                time.sleep(RATE_LIMIT_DELAY)
                product = publish_product(product_id)
                buy_url = product.get("short_url", short_url)
                urls[slug] = buy_url
                _save_urls(urls)
                print(f"  [live]   {slug} → {buy_url}")
                published += 1
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                print(f"  [error]  {slug} — {e}")
        else:
            # New product — create, attach, publish
            print(f"  [create] {slug} (${price_cents/100:.2f}) ...")
            try:
                product = create_product(
                    name=name,
                    description=description,
                    price_cents=price_cents,
                    file_path=str(pdf_path),
                )
                buy_url = product.get("short_url", "")
                urls[slug] = buy_url
                _save_urls(urls)
                print(f"  [live]   {slug} → {buy_url}")
                published += 1
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                print(f"  [error]  {slug} — {e}")

    print(f"\n[gumroad] Done. {published} published, {skipped} skipped.")
    print(f"[gumroad] URLs saved to products/urls.json")
