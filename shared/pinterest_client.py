"""
Pinterest API v5 client for creating pins that drive traffic to product listings.

Auth: OAuth2. Run `get_auth_url()`, open URL, exchange code via `exchange_code()`.
Tokens stored in kv_store under lane='system', key='pinterest_tokens'.
"""
import os
import json
import time
import secrets
import requests
from typing import Any

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
PINTEREST_AUTH_BASE = "https://www.pinterest.com/oauth"
SCOPES = "boards:read,boards:write,pins:read,pins:write"
REDIRECT_URI = "http://localhost:8000/pinterest/callback"


def _app_id() -> str:
    return os.environ["PINTEREST_APP_ID"]


def _app_secret() -> str:
    return os.environ["PINTEREST_APP_SECRET"]


def get_auth_url() -> tuple[str, str]:
    state = secrets.token_urlsafe(16)
    url = (
        f"{PINTEREST_AUTH_BASE}/"
        f"?client_id={_app_id()}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={SCOPES}"
        f"&state={state}"
    )
    return url, state


def exchange_code(code: str) -> dict[str, Any]:
    resp = requests.post(
        f"{PINTEREST_API_BASE}/oauth/token",
        auth=(_app_id(), _app_secret()),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    resp.raise_for_status()
    tokens = resp.json()
    tokens["expires_at"] = int(time.time()) + tokens.get("expires_in", 86400)
    _save_tokens(tokens)
    return tokens


def refresh_tokens(tokens: dict) -> dict:
    resp = requests.post(
        f"{PINTEREST_API_BASE}/oauth/token",
        auth=(_app_id(), _app_secret()),
        data={
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
    )
    resp.raise_for_status()
    new_tokens = resp.json()
    new_tokens["expires_at"] = int(time.time()) + new_tokens.get("expires_in", 86400)
    _save_tokens(new_tokens)
    return new_tokens


def _save_tokens(tokens: dict):
    from shared.db import db_session
    from sqlalchemy import text
    with db_session() as session:
        session.execute(
            text("""
                INSERT INTO kv_store (lane, key, value, updated_at)
                VALUES ('system', 'pinterest_tokens', :v::jsonb, NOW())
                ON CONFLICT (lane, key) DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
            """),
            {"v": json.dumps(tokens)},
        )


def _load_tokens() -> dict:
    from shared.db import db_session
    from sqlalchemy import text
    with db_session() as session:
        row = session.execute(
            text("SELECT value FROM kv_store WHERE lane='system' AND key='pinterest_tokens'")
        ).fetchone()
    if not row:
        raise RuntimeError("No Pinterest tokens. Run pinterest_auth.py first.")
    return row[0]


def _headers() -> dict[str, str]:
    tokens = _load_tokens()
    if int(time.time()) >= tokens.get("expires_at", 0) - 60:
        tokens = refresh_tokens(tokens)
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def get_or_create_board(board_name: str) -> str:
    """Return board_id for board_name, creating it if needed."""
    resp = requests.get(f"{PINTEREST_API_BASE}/boards", headers=_headers())
    resp.raise_for_status()
    boards = resp.json().get("items", [])
    for b in boards:
        if b["name"].lower() == board_name.lower():
            return b["id"]
    resp2 = requests.post(
        f"{PINTEREST_API_BASE}/boards",
        headers=_headers(),
        json={"name": board_name, "privacy": "PUBLIC"},
    )
    resp2.raise_for_status()
    return resp2.json()["id"]


def create_pin(
    board_id: str,
    title: str,
    description: str,
    link: str,
    image_url: str,
) -> dict[str, Any]:
    payload = {
        "board_id": board_id,
        "title": title[:100],
        "description": description[:500],
        "link": link,
        "media_source": {
            "source_type": "image_url",
            "url": image_url,
        },
    }
    resp = requests.post(f"{PINTEREST_API_BASE}/pins", headers=_headers(), json=payload)
    resp.raise_for_status()
    return resp.json()
