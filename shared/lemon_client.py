"""
Lemon Squeezy API client.
Docs: https://docs.lemonsqueezy.com/api

Get your API key: app.lemonsqueezy.com → Settings → API
Store ID: app.lemonsqueezy.com → Settings → Stores → copy the numeric ID
"""
import os
import requests
from typing import Any

LEMON_API_BASE = "https://api.lemonsqueezy.com/v1"


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['LEMON_API_KEY']}",
        "Accept": "application/vnd.api+json",
        "Content-Type": "application/vnd.api+json",
    }


def get_store_id() -> str:
    """Return the first store ID on the account (or LEMON_STORE_ID from env)."""
    store_id = os.environ.get("LEMON_STORE_ID")
    if store_id:
        return store_id
    resp = requests.get(f"{LEMON_API_BASE}/stores", headers=_headers())
    resp.raise_for_status()
    stores = resp.json().get("data", [])
    if not stores:
        raise RuntimeError("No Lemon Squeezy stores found. Create one at app.lemonsqueezy.com.")
    return stores[0]["id"]


def create_product(
    store_id: str,
    name: str,
    description: str,
    price_cents: int,
) -> dict[str, Any]:
    """Create a product. Returns product dict with id and buy_now_url."""
    payload = {
        "data": {
            "type": "products",
            "attributes": {
                "name": name,
                "description": description,
                "price": price_cents,
                "buy_now_pay_later": False,
                "enabled": True,
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(store_id)}}
            },
        }
    }
    resp = requests.post(f"{LEMON_API_BASE}/products", headers=_headers(), json=payload)
    resp.raise_for_status()
    return resp.json()["data"]


def create_variant(
    product_id: str,
    price_cents: int,
    name: str = "Default",
) -> dict[str, Any]:
    """Create a price variant for a product."""
    payload = {
        "data": {
            "type": "variants",
            "attributes": {
                "name": name,
                "price": price_cents,
                "is_membership": False,
                "interval": None,
                "interval_count": None,
                "trial_interval": None,
                "trial_interval_count": None,
            },
            "relationships": {
                "product": {"data": {"type": "products", "id": str(product_id)}}
            },
        }
    }
    resp = requests.post(f"{LEMON_API_BASE}/variants", headers=_headers(), json=payload)
    resp.raise_for_status()
    return resp.json()["data"]


def get_products(store_id: str | None = None) -> list[dict[str, Any]]:
    params = {}
    if store_id:
        params["filter[store_id]"] = store_id
    resp = requests.get(f"{LEMON_API_BASE}/products", headers=_headers(), params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])


def get_orders(store_id: str | None = None) -> list[dict[str, Any]]:
    params = {}
    if store_id:
        params["filter[store_id]"] = store_id
    resp = requests.get(f"{LEMON_API_BASE}/orders", headers=_headers(), params=params)
    resp.raise_for_status()
    return resp.json().get("data", [])
