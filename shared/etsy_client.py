"""
Etsy API v3 client.

Auth flow: OAuth2 PKCE. The first time you run this, call `get_auth_url()`
and open the URL, then exchange the code via `exchange_code(code, state)`.
Tokens are stored in the DB kv_store under lane='system', key='etsy_tokens'.
"""
import os
import json
import time
import secrets
import hashlib
import base64
import requests
from typing import Any

ETSY_API_BASE = "https://openapi.etsy.com/v3"
ETSY_AUTH_BASE = "https://www.etsy.com/oauth"
SCOPES = "listings_r listings_w listings_d shops_r transactions_r"
REDIRECT_URI = "http://localhost:8000/etsy/callback"  # update when deployed


def _keyid() -> str:
    return os.environ["ETSY_KEYSTRING"]


# ── OAuth helpers ──────────────────────────────────────────────────────────────

def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def get_auth_url() -> tuple[str, str, str]:
    """Return (url, state, verifier). Store state+verifier; send user to url."""
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(16)
    url = (
        f"{ETSY_AUTH_BASE}/connect"
        f"?response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={SCOPES.replace(' ', '%20')}"
        f"&client_id={_keyid()}"
        f"&state={state}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
    )
    return url, state, verifier


def exchange_code(code: str, verifier: str) -> dict[str, Any]:
    resp = requests.post(
        f"{ETSY_AUTH_BASE}/token",
        data={
            "grant_type": "authorization_code",
            "client_id": _keyid(),
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "code_verifier": verifier,
        },
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens["expires_at"] = int(time.time()) + tokens["expires_in"]
    _save_tokens(tokens)
    return tokens


def refresh_tokens(tokens: dict) -> dict:
    resp = requests.post(
        f"{ETSY_AUTH_BASE}/token",
        data={
            "grant_type": "refresh_token",
            "client_id": _keyid(),
            "refresh_token": tokens["refresh_token"],
        },
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    new_tokens["expires_at"] = int(time.time()) + new_tokens["expires_in"]
    _save_tokens(new_tokens)
    return new_tokens


def _save_tokens(tokens: dict):
    from shared.db import db_session
    from sqlalchemy import text
    with db_session() as session:
        session.execute(
            text("""
                INSERT INTO kv_store (lane, key, value, updated_at)
                VALUES ('system', 'etsy_tokens', :v::jsonb, NOW())
                ON CONFLICT (lane, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """),
            {"v": json.dumps(tokens)},
        )


def _load_tokens() -> dict:
    from shared.db import db_session
    from sqlalchemy import text
    with db_session() as session:
        row = session.execute(
            text("SELECT value FROM kv_store WHERE lane='system' AND key='etsy_tokens'")
        ).fetchone()
    if not row:
        raise RuntimeError("No Etsy tokens found. Run etsy_auth.py to authenticate.")
    return row[0]


def _auth_headers() -> dict[str, str]:
    tokens = _load_tokens()
    if int(time.time()) >= tokens.get("expires_at", 0) - 60:
        tokens = refresh_tokens(tokens)
    return {
        "Authorization": f"Bearer {tokens['access_token']}",
        "x-api-key": _keyid(),
    }


# ── Listing helpers ────────────────────────────────────────────────────────────

def get_shop_id() -> int:
    resp = requests.get(f"{ETSY_API_BASE}/application/openapi-ping", headers=_auth_headers())
    resp.raise_for_status()
    resp2 = requests.get(f"{ETSY_API_BASE}/application/users/me", headers=_auth_headers())
    resp2.raise_for_status()
    shop_id = resp2.json()["shop_id"]
    return shop_id


def create_draft_listing(
    shop_id: int,
    title: str,
    description: str,
    price_usd: float,
    tags: list[str],
    digital: bool = True,
) -> dict[str, Any]:
    """Create a draft listing (must upload file and then publish separately)."""
    payload = {
        "quantity": 999,
        "title": title[:140],
        "description": description,
        "price": price_usd,
        "who_made": "i_did",
        "when_made": "made_to_order",
        "taxonomy_id": 2078,  # Digital > Templates
        "tags": tags[:13],
        "is_digital": digital,
        "should_auto_renew": True,
        "listing_type": "download" if digital else "physical",
        "shipping_profile_id": None if digital else 0,
    }
    resp = requests.post(
        f"{ETSY_API_BASE}/application/shops/{shop_id}/listings",
        headers=_auth_headers(),
        json=payload,
    )
    resp.raise_for_status()
    return resp.json()


def upload_listing_file(shop_id: int, listing_id: int, file_path: str) -> dict[str, Any]:
    with open(file_path, "rb") as f:
        resp = requests.post(
            f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/{listing_id}/files",
            headers=_auth_headers(),
            files={"file": f},
        )
    resp.raise_for_status()
    return resp.json()


def publish_listing(shop_id: int, listing_id: int) -> dict[str, Any]:
    resp = requests.patch(
        f"{ETSY_API_BASE}/application/shops/{shop_id}/listings/{listing_id}",
        headers=_auth_headers(),
        json={"state": "active"},
    )
    resp.raise_for_status()
    return resp.json()
