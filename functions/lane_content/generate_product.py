"""
Content Lane -- Digital Product Generator (two-pass).

Pass 1: Claude Opus designs the product structure (sections + metadata).
Pass 2: Claude Sonnet fills in each section's prompts individually.
Final:  Renders branded PDF → auto-publishes to Lemon Squeezy → lists on Etsy → updates Pinterest CSV.

Run: python run.py content:generate
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.pdf_builder import build_prompt_pack

BRAND_NAME = "Hone"
BRAND_TAGLINE = "Sharpen your AI output."
PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"

# -- Pass 1: structure schema ---------------------------------------------------
STRUCTURE_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "title":       {"type": "string", "description": "PDF cover title -- benefit-driven"},
        "subtitle":    {"type": "string", "description": "e.g. '47 ready-to-use prompts for landing better clients faster'"},
        "slug":        {"type": "string", "description": "lowercase-kebab-case filename, e.g. 'freelance-client-acquisition'"},
        "store_name":  {"type": "string", "description": "Store listing name, 60 chars max"},
        "store_description": {
            "type": "string",
            "description": "200-300 word store description. Pain → bullets of what's inside → format + compatibility. Plain text."
        },
        "price_cents": {"type": "integer", "description": "1700, 2700, or 3700"},
        "intro":       {"type": "string", "description": "80-120 word PDF intro paragraph"},
        "bonus_tips":  {"type": "array", "minItems": 5, "maxItems": 7, "items": {"type": "string"}},
        "etsy_tags":   {"type": "array", "maxItems": 13, "items": {"type": "string", "maxLength": 20}},
        "sections": {
            "type": "array",
            "minItems": 5,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "name":        {"type": "string"},
                    "description": {"type": "string", "description": "1-2 sentences on what this section covers"},
                    "prompt_labels": {
                        "type": "array",
                        "minItems": 7,
                        "maxItems": 9,
                        "items": {
                            "type": "object",
                            "properties": {
                                "label":    {"type": "string", "description": "Short label, e.g. 'Cold outreach opener'"},
                                "use_case": {"type": "string", "description": "One sentence: when to use this and what outcome it produces"}
                            },
                            "required": ["label", "use_case"]
                        }
                    }
                },
                "required": ["name", "description", "prompt_labels"]
            }
        }
    },
    "required": ["title", "subtitle", "slug", "store_name", "store_description",
                 "price_cents", "intro", "bonus_tips", "etsy_tags", "sections"]
})

# -- Pass 2: prompts schema (per section) --------------------------------------
PROMPTS_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label":    {"type": "string"},
                    "prompt":   {
                        "type": "string",
                        "description": (
                            "Complete, paste-ready prompt. Full sentences. Specific instructions. "
                            "Use [BRACKETS] only for truly unavoidable variables like [company name]. "
                            "Minimum 3 sentences. Zero editing required by buyer."
                        )
                    },
                    "use_case": {"type": "string"}
                },
                "required": ["label", "prompt", "use_case"]
            }
        }
    },
    "required": ["prompts"]
})

NICHES = [
    "freelance client acquisition and outreach",
    "LinkedIn content creation and personal brand building",
    "email marketing and newsletter writing",
    "e-commerce product listings and Etsy shop optimization",
    "YouTube script writing and channel growth",
    "solopreneur business planning and strategy",
    "social media content creation for coaches and consultants",
    "podcast guest outreach and show growth",
    "job search, resume writing, and interview prep",
    "real estate agent marketing and client communication",
    "online course creation and launch marketing",
    "SaaS founder go-to-market and cold outreach",
    "copywriting for landing pages and sales pages",
    "Twitter/X growth and audience building",
    "virtual assistant and service business scaling",
    "Notion workspace setup and productivity systems",
    "agency client onboarding and project management",
    "creator economy and monetizing an audience",
]


def pick_niche(existing_slugs: set[str]) -> str:
    # Normalize both sides: lowercase, strip hyphens so "e-commerce" matches "ecommerce" in slug
    norm_slugs = [s.lower().replace("-", "") for s in existing_slugs]
    for niche in NICHES:
        keyword = niche.split()[0].lower().replace("-", "")
        if not any(keyword in slug for slug in norm_slugs):
            return niche
    return NICHES[len(existing_slugs) % len(NICHES)]


def get_existing_slugs() -> set[str]:
    PRODUCTS_DIR.mkdir(exist_ok=True)
    return {p.stem for p in PRODUCTS_DIR.glob("*.pdf")}


def run() -> dict:
    existing_slugs = get_existing_slugs()
    niche = pick_niche(existing_slugs)
    print(f"\n[generate] Niche    : {niche}")
    print(f"[generate] Catalog  : {len(existing_slugs)} existing products")

    # -- Pass 1: design structure -----------------------------------------------
    print("[generate] Pass 1/2 -- designing product structure (Opus)...")
    structure = orchestrate(
        lane="content",
        task="Design a complete Hone prompt pack structure for the given niche.",
        context={
            "brand": BRAND_NAME,
            "tagline": BRAND_TAGLINE,
            "niche": niche,
            "target_buyer": "founder, freelancer, or solopreneur using Claude or ChatGPT daily",
            "goal": (
                "Create 5-6 sections with 7-9 prompt slots each (labels + use cases only, "
                "not the prompt text yet). Choose $17/$27/$37 pricing based on depth. "
                "Make every label specific and actionable."
            ),
            "date": datetime.now(timezone.utc).isoformat(),
        },
        response_schema=STRUCTURE_SCHEMA,
        use_opus=True,
    )

    # -- Pass 2: write prompts section by section -------------------------------
    print(f"[generate] Pass 2/2 -- writing prompts for {len(structure['sections'])} sections (Sonnet)...")
    full_sections = []
    for i, section in enumerate(structure["sections"]):
        print(f"           Section {i+1}/{len(structure['sections'])}: {section['name']}")
        result = orchestrate(
            lane="content",
            task="Write the complete prompt text for each slot in this section.",
            context={
                "product_title": structure["title"],
                "niche": niche,
                "section_name": section["name"],
                "section_description": section["description"],
                "prompt_slots": section["prompt_labels"],
                "instruction": (
                    "Write a complete, paste-ready prompt for each slot. "
                    "Each prompt must be self-contained with full instructions -- "
                    "the buyer should get a real, useful output with zero extra thinking. "
                    "Minimum 3 sentences per prompt."
                ),
            },
            response_schema=PROMPTS_SCHEMA,
            use_opus=False,
        )
        full_sections.append({
            "name": section["name"],
            "description": section["description"],
            "prompts": result["prompts"],
        })

    # -- Assemble final product -------------------------------------------------
    product_data = {
        **structure,
        "sections": full_sections,
        "brand": BRAND_NAME,
        "tagline": BRAND_TAGLINE,
    }

    slug = product_data.get("slug", "product")
    # Avoid overwriting an existing product — append suffix if slug collides
    base_slug = slug
    counter = 2
    while (PRODUCTS_DIR / f"{slug}.pdf").exists():
        slug = f"{base_slug}-{counter}"
        counter += 1
    product_data["slug"] = slug
    pdf_path = str(PRODUCTS_DIR / f"{slug}.pdf")
    meta_path = str(PRODUCTS_DIR / f"{slug}.json")

    print("[generate] Rendering PDF...")
    build_prompt_pack(pdf_path, product_data)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(product_data, f, indent=2, ensure_ascii=False)

    price = product_data["price_cents"] / 100
    prompt_count = sum(len(s.get("prompts", [])) for s in full_sections)

    print(f"\n{'='*55}")
    print(f"  PRODUCT READY: {product_data['title']}")
    print(f"  Price: ${price:.2f}  |  {prompt_count} prompts  |  {len(full_sections)} sections")
    print(f"{'='*55}")

    # -- Auto-publish pipeline --------------------------------------------------
    lemon_url = _try_publish_to_lemon(product_data, pdf_path)
    _try_publish_to_etsy(product_data, pdf_path)
    _append_to_pinterest_csv(product_data, lemon_url)

    return product_data


def _try_publish_to_lemon(product_data: dict, pdf_path: str) -> str:
    """Publish to Lemon Squeezy. Returns buy_now_url or empty string."""
    lemon_key = os.environ.get("LEMON_API_KEY", "")
    if not lemon_key or lemon_key.startswith("..."):
        print("  [lemon] Skipped -- add LEMON_API_KEY to .env to auto-publish")
        return ""
    try:
        from shared.lemon_client import get_store_id, create_product
        from shared.db import db_session
        from sqlalchemy import text

        store_id = get_store_id()
        product = create_product(
            store_id=store_id,
            name=product_data["store_name"],
            description=product_data["store_description"],
            price_cents=product_data["price_cents"],
        )
        buy_url = product.get("attributes", {}).get("buy_now_url", "")
        product_id = product.get("id", "")

        with db_session() as session:
            import json as _json
            session.execute(
                text("""
                    INSERT INTO kv_store (lane, key, value, updated_at)
                    VALUES ('content', :key, :val::jsonb, NOW())
                    ON CONFLICT (lane, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                """),
                {
                    "key": f"lemon_product_{product_data['slug']}",
                    "val": _json.dumps({
                        "product_id": str(product_id),
                        "buy_now_url": buy_url,
                        "slug": product_data["slug"],
                    }),
                },
            )

        print(f"  [lemon] Live: {buy_url}")
        print(f"  [lemon] Upload PDF at: app.lemonsqueezy.com -> Products -> Files")
        return buy_url
    except Exception as e:
        print(f"  [lemon] Failed: {e}")
        return ""


def _try_publish_to_etsy(product_data: dict, pdf_path: str):
    """Auto-list on Etsy if credentials are available."""
    etsy_key = os.environ.get("ETSY_KEYSTRING", "")
    if not etsy_key or etsy_key.startswith("..."):
        print("  [etsy] Skipped -- add ETSY_KEYSTRING to .env to auto-list")
        return
    try:
        from functions.lane_content.publish_to_etsy import publish_product_to_etsy
        publish_product_to_etsy(product_data, pdf_path)
    except RuntimeError as e:
        if "No Etsy tokens" in str(e):
            print("  [etsy] Skipped -- run: python run.py content:etsy-auth to connect your shop")
        else:
            print(f"  [etsy] Failed: {e}")
    except Exception as e:
        print(f"  [etsy] Failed: {e}")


def _append_to_pinterest_csv(product_data: dict, buy_url: str):
    """Add pins for the new product to the Pinterest schedule CSV."""
    try:
        from functions.lane_content.pin_products import generate_pins_for_product
        from pathlib import Path
        import csv

        output_path = Path(__file__).resolve().parents[2] / "brand" / "pinterest_schedule.csv"
        output_path.parent.mkdir(exist_ok=True)

        pins = generate_pins_for_product(product_data, buy_url, count=3)

        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        slots = [now + timedelta(hours=i * 12) for i in range(3)]

        headers = ["Title", "Description", "Link", "Board", "Publish Date", "Image Headline", "Image Subtext"]
        write_header = not output_path.exists()
        with open(output_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if write_header:
                writer.writerow(headers)
            for pin, slot in zip(pins, slots):
                writer.writerow([
                    pin["title"],
                    pin["description"],
                    pin.get("product_url", buy_url),
                    pin["board_name"],
                    slot.strftime("%Y-%m-%dT%H:%M:%S"),
                    pin["image_headline"],
                    pin["image_subtext"],
                ])
        print(f"  [pinterest] 3 pins appended to brand/pinterest_schedule.csv")
    except Exception as e:
        print(f"  [pinterest] Failed: {e}")


if __name__ == "__main__":
    run()
