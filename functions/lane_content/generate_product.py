"""
Content Lane — Digital Product Generator.

Asks Claude to design and write a complete digital product (prompt pack, template set,
or guide), renders it as a PDF, and publishes it to Gumroad.

Run locally:  python -m functions.lane_content.generate_product
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.claude_client import orchestrate
from shared.gumroad_client import create_product, get_products
from shared.pdf_builder import build_prompt_pack

PRODUCT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "product_type": {"type": "string", "enum": ["prompt_pack", "template_set", "guide"]},
        "title": {"type": "string", "description": "Compelling, benefit-driven product title"},
        "subtitle": {"type": "string"},
        "gumroad_name": {"type": "string", "description": "Short product name for Gumroad listing"},
        "gumroad_description": {"type": "string", "description": "Gumroad product description — lead with the pain, then the solution, 150-250 words, plain text"},
        "price_cents": {"type": "integer", "description": "Price in cents (e.g. 2700 = $27)"},
        "intro": {"type": "string", "description": "PDF intro paragraph, 80-120 words"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "prompts": {
                        "type": "array",
                        "minItems": 5,
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "prompt": {"type": "string", "description": "The actual prompt text, ready to paste into Claude or ChatGPT"},
                                "use_case": {"type": "string"}
                            }
                        }
                    }
                }
            }
        },
        "bonus_tips": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 5
        }
    },
    "required": ["title", "subtitle", "gumroad_name", "gumroad_description", "price_cents", "intro", "sections", "bonus_tips"]
})

NICHES = [
    "solopreneur productivity",
    "AI-powered content creation for coaches",
    "freelance client acquisition",
    "e-commerce product listing optimization",
    "podcast growth and monetization",
    "LinkedIn personal brand building",
    "email newsletter growth",
    "SaaS founder go-to-market",
    "YouTube creator scripting and SEO",
    "Etsy shop optimization with AI",
]


def pick_niche(existing_products: list[dict]) -> str:
    """Pick the niche not yet covered by existing products."""
    existing_titles = {p.get("name", "").lower() for p in existing_products}
    for niche in NICHES:
        if not any(niche.split()[0] in t for t in existing_titles):
            return niche
    return NICHES[len(existing_products) % len(NICHES)]


def run():
    existing = get_products()
    niche = pick_niche(existing)
    print(f"[lane_content] Generating product for niche: {niche}")

    context = {
        "niche": niche,
        "existing_product_count": len(existing),
        "target_buyer": "solopreneur or founder who uses AI tools daily",
        "goal": "Create a prompt pack with 30+ ready-to-use prompts across 5-6 sections. "
                "Every prompt must be immediately usable — no placeholders that need editing. "
                "Price between $17 and $37. Prioritize prompts that save >1 hour of work.",
        "date": datetime.now(timezone.utc).isoformat(),
    }

    print("[lane_content] Calling Claude (opus) to design product...")
    product_data = orchestrate(
        lane="content",
        task="Design and write a complete, immediately sellable digital product for the given niche.",
        context=context,
        response_schema=PRODUCT_SCHEMA,
        use_opus=True,
    )

    # Build PDF
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "product.pdf")
        print(f"[lane_content] Building PDF...")
        build_prompt_pack(pdf_path, product_data)

        # Publish to Gumroad
        print(f"[lane_content] Publishing to Gumroad: {product_data['gumroad_name']}")
        gum_product = create_product(
            name=product_data["gumroad_name"],
            description=product_data["gumroad_description"],
            price_cents=product_data["price_cents"],
            file_path=pdf_path,
        )

    print(f"[lane_content] LIVE: {gum_product.get('short_url')} — ${product_data['price_cents']/100:.2f}")
    return gum_product


if __name__ == "__main__":
    run()
