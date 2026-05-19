"""Gumroad API v2 client for publishing and monitoring digital products."""
import os
import requests
from typing import Any


GUMROAD_API_BASE = "https://api.gumroad.com/v2"


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {os.environ['GUMROAD_ACCESS_TOKEN']}"}


def create_product(
    name: str,
    description: str,
    price_cents: int,
    file_path: str | None = None,
) -> dict[str, Any]:
    """Create a new Gumroad product and return the product dict."""
    data = {
        "name": name,
        "description": description,
        "price": price_cents,
        "published": False,  # draft first, publish after file upload
    }
    resp = requests.post(f"{GUMROAD_API_BASE}/products", headers=_headers(), data=data)
    resp.raise_for_status()
    product = resp.json()["product"]

    if file_path:
        attach_file(product["id"], file_path)
        publish_product(product["id"])

    return product


def attach_file(product_id: str, file_path: str) -> dict[str, Any]:
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{GUMROAD_API_BASE}/products/{product_id}/product_files",
            headers=_headers(),
            files={"file": f},
        )
    resp.raise_for_status()
    return resp.json()


def publish_product(product_id: str) -> dict[str, Any]:
    resp = requests.put(
        f"{GUMROAD_API_BASE}/products/{product_id}",
        headers=_headers(),
        data={"published": True},
    )
    resp.raise_for_status()
    return resp.json()["product"]


def get_sales(product_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch recent sales. Pass product_id to filter."""
    params = {}
    if product_id:
        params["product_id"] = product_id
    resp = requests.get(f"{GUMROAD_API_BASE}/sales", headers=_headers(), params=params)
    resp.raise_for_status()
    return resp.json().get("sales", [])


def get_products() -> list[dict[str, Any]]:
    resp = requests.get(f"{GUMROAD_API_BASE}/products", headers=_headers())
    resp.raise_for_status()
    return resp.json().get("products", [])
