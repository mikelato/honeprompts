"""
Regenerate the product grid in docs/index.html from products/*.json.
Run after generating new products or when store URLs change.

Run: python run.py content:website
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

PRODUCTS_DIR = Path(__file__).resolve().parents[2] / "products"
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"
INDEX_HTML = DOCS_DIR / "index.html"

NICHE_TAGS = {
    "freelance": "Freelancing",
    "linkedin": "LinkedIn",
    "email": "Email Marketing",
    "ecommerce": "E-Commerce",
    "etsy": "Etsy",
    "youtube": "YouTube",
    "solopreneur": "Solopreneur",
    "social": "Social Media",
    "podcast": "Podcasting",
    "job": "Job Search",
    "real": "Real Estate",
    "online": "Online Courses",
    "saas": "SaaS",
    "copy": "Copywriting",
    "twitter": "Twitter / X",
    "virtual": "VA Business",
    "notion": "Notion",
    "agency": "Agency",
    "creator": "Creator Economy",
}


def _tag(slug: str) -> str:
    for key, label in NICHE_TAGS.items():
        if key in slug.lower():
            return label
    return "AI Prompts"


def _get_buy_url(slug: str) -> str:
    # Check local urls.json first (populated after manual listing)
    urls_file = PRODUCTS_DIR / "urls.json"
    if urls_file.exists():
        try:
            with open(urls_file, encoding="utf-8") as f:
                urls = json.load(f)
            url = urls.get(slug, "#")
            if url and url != "#":
                return url
        except Exception:
            pass
    # Fall back to DB (Lemon Squeezy buy_now_url)
    try:
        from shared.db import db_session
        from sqlalchemy import text
        with db_session() as session:
            row = session.execute(
                text("SELECT value FROM kv_store WHERE lane='content' AND key=:k"),
                {"k": f"lemon_product_{slug}"},
            ).fetchone()
        if row and row[0]:
            return row[0].get("buy_now_url", "#")
    except Exception:
        pass
    return "#"


def _card(p: dict) -> str:
    slug = p.get("slug", "")
    title = p.get("title", "")
    intro = p.get("intro", "")[:120].rstrip() + "..."
    price = p.get("price_cents", 2700) // 100
    sections = p.get("sections", [])
    prompt_count = sum(len(s.get("prompts", [])) for s in sections)
    tag = _tag(slug)
    buy_url = _get_buy_url(slug)

    return f"""      <div class="product-card">
        <span class="product-tag">{tag}</span>
        <h3>{title}</h3>
        <p>{intro}</p>
        <div class="product-meta">
          <div>
            <div class="product-price">${price}</div>
            <div class="product-count">{prompt_count} prompts &middot; {len(sections)} sections</div>
          </div>
          <a href="{buy_url}" class="product-btn">Get it</a>
        </div>
      </div>"""


def run(domain: str | None = None):
    json_files = sorted(f for f in PRODUCTS_DIR.glob("*.json") if f.name != "urls.json")
    if not json_files:
        print("[website] No products found.")
        return

    products = []
    for f in json_files:
        with open(f, encoding="utf-8") as fp:
            products.append(json.load(fp))

    # Sort by price desc, then title
    products.sort(key=lambda p: (-p.get("price_cents", 0), p.get("title", "")))

    cards_html = "\n".join(_card(p) for p in products)
    grid_block = f'    <div class="product-grid">\n{cards_html}\n    </div>'

    html = INDEX_HTML.read_text(encoding="utf-8")

    # Replace the product grid
    html = re.sub(
        r'<div class="product-grid">.*?</div>\s*</section>',
        f'{grid_block}\n  </div>\n</section>',
        html,
        flags=re.DOTALL,
    )

    # Update stats
    total_prompts = sum(
        sum(len(s.get("prompts", [])) for s in p.get("sections", []))
        for p in products
    )
    html = re.sub(r'(<div class="stat-num">)\d+\+?(</div>\s*<div class="stat-label">Ready-to-use)',
                  rf'\g<1>{total_prompts}+\2', html)
    html = re.sub(r'(<div class="stat-num">)\d+\+?(</div>\s*<div class="stat-label">Niche packs)',
                  rf'\g<1>{len(products)}+\2', html)

    # Update domain if provided
    if domain:
        html = html.replace("gethone.co", domain)
        html = html.replace("hello@gethone.co", f"hello@{domain}")

    INDEX_HTML.write_text(html, encoding="utf-8")

    # Also write CNAME for GitHub Pages custom domain
    if domain:
        (DOCS_DIR / "CNAME").write_text(domain, encoding="utf-8")
        print(f"[website] CNAME written: {domain}")

    print(f"[website] docs/index.html updated")
    print(f"[website] {len(products)} products, {total_prompts}+ prompts")
    for p in products:
        slug = p.get('slug','')
        url = _get_buy_url(slug)
        status = "LIVE" if url != "#" else "no URL yet"
        print(f"  {slug:<45} [{status}]")


if __name__ == "__main__":
    domain_arg = sys.argv[2] if len(sys.argv) > 2 else None
    run(domain_arg)
