"""
Content Lane — Digital Product Generator (two-pass).

Pass 1: Claude Opus designs the product structure (sections + metadata).
Pass 2: Claude Sonnet fills in each section's prompts individually.
Final:  Renders branded PDF, saves locally, auto-publishes if Lemon Squeezy is configured.

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

# ── Pass 1: structure schema ───────────────────────────────────────────────────
STRUCTURE_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "title":       {"type": "string", "description": "PDF cover title — benefit-driven"},
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

# ── Pass 2: prompts schema (per section) ──────────────────────────────────────
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
]


def pick_niche(existing_slugs: set[str]) -> str:
    for niche in NICHES:
        keyword = niche.split()[0]
        if not any(keyword in s for s in existing_slugs):
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

    # ── Pass 1: design structure ───────────────────────────────────────────────
    print("[generate] Pass 1/2 — designing product structure (Opus)...")
    structure = orchestrate(
        lane="content",
        task="Design a complete PromptVault prompt pack structure for the given niche.",
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

    # ── Pass 2: write prompts section by section ───────────────────────────────
    print(f"[generate] Pass 2/2 — writing prompts for {len(structure['sections'])} sections (Sonnet)...")
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
                    "Each prompt must be self-contained with full instructions — "
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

    # ── Assemble final product ─────────────────────────────────────────────────
    product_data = {
        **structure,
        "sections": full_sections,
        "brand": BRAND_NAME,
        "tagline": BRAND_TAGLINE,
    }

    slug = product_data.get("slug", "product")
    pdf_path = str(PRODUCTS_DIR / f"{slug}.pdf")
    meta_path = str(PRODUCTS_DIR / f"{slug}.json")

    print("[generate] Rendering PDF...")
    build_prompt_pack(pdf_path, product_data)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(product_data, f, indent=2, ensure_ascii=False)

    price = product_data["price_cents"] / 100
    prompt_count = sum(len(s.get("prompts", [])) for s in full_sections)

    print(f"\n{'='*55}")
    print(f"  PRODUCT READY")
    print(f"{'='*55}")
    print(f"  Title    : {product_data['title']}")
    print(f"  Price    : ${price:.2f}")
    print(f"  Prompts  : {prompt_count} across {len(full_sections)} sections")
    print(f"  PDF      : products/{slug}.pdf")
    print(f"{'='*55}")
    print()
    print("  NEXT — list it:")
    print("  Option A (auto): add LEMON_API_KEY + LEMON_STORE_ID to .env")
    print("                   then run: python run.py content:publish")
    print("  Option B (Etsy manual):")
    print(f"    Title : {product_data['store_name']}")
    print(f"    Price : ${price:.2f}")
    print(f"    Tags  : {', '.join(product_data.get('etsy_tags', []))}")
    print(f"    Desc  : see products/{slug}.json → store_description")
    print(f"{'='*55}\n")

    # Auto-publish to Lemon Squeezy if configured
    lemon_key = os.environ.get("LEMON_API_KEY", "")
    if lemon_key and not lemon_key.startswith("..."):
        _publish_to_lemon(product_data, pdf_path)

    return product_data


def _publish_to_lemon(product_data: dict, pdf_path: str):
    from shared.lemon_client import get_store_id, create_product
    try:
        store_id = get_store_id()
        product = create_product(
            store_id=store_id,
            name=product_data["store_name"],
            description=product_data["store_description"],
            price_cents=product_data["price_cents"],
        )
        url = product.get("attributes", {}).get("buy_now_url", "")
        print(f"  ✓ Live on Lemon Squeezy: {url}")
        print(f"  Upload PDF: app.lemonsqueezy.com → Products → Files")
    except Exception as e:
        print(f"  Lemon Squeezy publish failed: {e}")


if __name__ == "__main__":
    run()
