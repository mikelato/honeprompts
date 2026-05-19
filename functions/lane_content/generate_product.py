"""
Content Lane — Digital Product Generator.

Asks Claude to design and write a complete digital product (prompt pack),
renders it as a branded PromptVault PDF, and publishes it to Gumroad.

Run locally:  python run.py content:generate
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

BRAND_NAME = "PromptVault"
BRAND_TAGLINE = "Ready-to-use AI prompts for people who build things."

PRODUCT_SCHEMA = json.dumps({
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "PDF cover title — benefit-driven, e.g. 'The Freelance Client Acquisition Prompt Pack'"
        },
        "subtitle": {
            "type": "string",
            "description": "PDF subtitle — what they get, e.g. '42 ready-to-use prompts for landing better clients faster'"
        },
        "gumroad_name": {
            "type": "string",
            "description": "Short Gumroad product name (60 chars max)"
        },
        "gumroad_description": {
            "type": "string",
            "description": (
                "Gumroad/Etsy product description. Lead with the pain point. "
                "List what's inside with bullet points. End with format + compatibility note. "
                "200-300 words. Plain text only."
            )
        },
        "price_cents": {
            "type": "integer",
            "description": "Price in cents. Use $17, $27, or $37 — pick based on prompt count and depth."
        },
        "intro": {
            "type": "string",
            "description": "PDF intro paragraph, 80-120 words. Speak to the reader's frustration, then promise the solution."
        },
        "sections": {
            "type": "array",
            "minItems": 5,
            "maxItems": 7,
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string", "description": "1-2 sentences on what this section covers"},
                    "prompts": {
                        "type": "array",
                        "minItems": 6,
                        "maxItems": 10,
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "description": "Short label, e.g. 'Cold outreach opener'"},
                                "prompt": {
                                    "type": "string",
                                    "description": (
                                        "The actual prompt text — complete, ready to paste into Claude or ChatGPT. "
                                        "Use [BRACKETS] only for unavoidable variables like [company name]. "
                                        "Must be immediately usable with zero editing."
                                    )
                                },
                                "use_case": {
                                    "type": "string",
                                    "description": "One sentence: when to use this prompt and what outcome it produces"
                                }
                            },
                            "required": ["label", "prompt", "use_case"]
                        }
                    }
                },
                "required": ["name", "description", "prompts"]
            }
        },
        "bonus_tips": {
            "type": "array",
            "minItems": 5,
            "maxItems": 8,
            "items": {
                "type": "string",
                "description": "Actionable tip for getting better results from AI prompts"
            }
        },
        "etsy_tags": {
            "type": "array",
            "maxItems": 13,
            "items": {"type": "string", "maxLength": 20},
            "description": "Etsy SEO tags — single words or two-word phrases, no special chars"
        }
    },
    "required": [
        "title", "subtitle", "gumroad_name", "gumroad_description",
        "price_cents", "intro", "sections", "bonus_tips", "etsy_tags"
    ]
})

# Niches ordered by Etsy/Gumroad search demand and buyer intent
NICHES = [
    "freelance client acquisition and outreach",
    "LinkedIn content creation and personal brand",
    "email marketing and newsletter writing",
    "e-commerce product listings and Etsy shop optimization",
    "YouTube script writing and channel growth",
    "solopreneur business planning and strategy",
    "social media content creation for coaches",
    "podcast guest outreach and show growth",
    "job search, resume writing, and interview prep",
    "Etsy seller marketing and product launch",
    "real estate agent marketing and client communication",
    "online course creation and launch",
]


def pick_niche(existing_products: list[dict]) -> str:
    existing_names = " ".join(p.get("name", "").lower() for p in existing_products)
    for niche in NICHES:
        keyword = niche.split()[0]
        if keyword not in existing_names:
            return niche
    return NICHES[len(existing_products) % len(NICHES)]


def run():
    existing = get_products()
    niche = pick_niche(existing)
    print(f"[lane_content] Niche selected: {niche}")
    print(f"[lane_content] Existing products: {len(existing)}")

    context = {
        "brand": BRAND_NAME,
        "tagline": BRAND_TAGLINE,
        "niche": niche,
        "target_buyer": "founder, freelancer, or solopreneur who uses Claude or ChatGPT daily",
        "goal": (
            "Design a complete, immediately sellable prompt pack. "
            "Every prompt must be ready to paste — no placeholders except unavoidable variables like [company name]. "
            "Aim for 40-60 total prompts across 5-7 sections. "
            "Price at $17, $27, or $37 based on depth — err toward $27."
        ),
        "date": datetime.now(timezone.utc).isoformat(),
    }

    print("[lane_content] Generating product with Claude Opus...")
    product_data = orchestrate(
        lane="content",
        task="Design and write a complete, immediately sellable PromptVault digital product for the given niche.",
        context=context,
        response_schema=PRODUCT_SCHEMA,
        use_opus=True,
    )

    # Inject brand into PDF metadata
    product_data["brand"] = BRAND_NAME
    product_data["tagline"] = BRAND_TAGLINE

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, "product.pdf")
        print("[lane_content] Building PDF...")
        build_prompt_pack(pdf_path, product_data)

        print(f"[lane_content] Publishing to Gumroad: {product_data['gumroad_name']}")
        gum_product = create_product(
            name=product_data["gumroad_name"],
            description=product_data["gumroad_description"],
            price_cents=product_data["price_cents"],
            file_path=pdf_path,
        )

    url = gum_product.get("short_url", "")
    price = product_data["price_cents"] / 100
    print(f"\n✓ LIVE on Gumroad: {url} — ${price:.2f}")
    print(f"  Etsy tags ready: {', '.join(product_data.get('etsy_tags', []))}")
    print(f"  Next: python run.py content:pin\n")
    return gum_product


if __name__ == "__main__":
    run()
