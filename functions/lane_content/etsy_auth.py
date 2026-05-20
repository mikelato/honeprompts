"""
Etsy OAuth2 PKCE auth flow -- run once to connect your Etsy shop.

Step 1: python run.py content:etsy-auth
        Copy the URL and open it in your browser. Log in and approve.
        You'll be redirected to localhost:8000/etsy/callback?code=...&state=...
        Copy the `code` and `state` values from the URL.

Step 2: python run.py content:etsy-auth <code> <state>
        This exchanges the code for tokens and saves them to .etsy_tokens.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.etsy_client import get_auth_url, exchange_code

STATE_FILE = Path(__file__).resolve().parents[2] / ".etsy_oauth_state.json"
TOKENS_FILE = Path(__file__).resolve().parents[2] / ".etsy_tokens.json"


def _save_state(verifier: str, state: str):
    STATE_FILE.write_text(json.dumps({"verifier": verifier, "state": state}))


def _load_state() -> tuple[str, str]:
    if not STATE_FILE.exists():
        raise RuntimeError("No pending OAuth session. Run step 1 first.")
    data = json.loads(STATE_FILE.read_text())
    return data["verifier"], data["state"]


def run(code: str | None = None, state: str | None = None):
    if not code:
        url, state_val, verifier = get_auth_url()
        _save_state(verifier, state_val)
        print("\n  ETSY AUTH - STEP 1 OF 2")
        print("  -------------------------------------------------")
        print("  Open this URL in your browser:\n")
        print(f"  {url}\n")
        print("  After approving, you'll land on localhost:8000/etsy/callback")
        print("  Copy the `code` and `state` from the URL, then run:\n")
        print("  python run.py content:etsy-auth <code> <state>\n")
    else:
        verifier, saved_state = _load_state()
        if state and state != saved_state:
            raise RuntimeError("State mismatch. Start the auth flow again.")
        tokens = exchange_code(code, verifier)
        TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
        try:
            from shared.etsy_client import _save_tokens
            _save_tokens(tokens)
        except Exception:
            pass
        STATE_FILE.unlink(missing_ok=True)
        print("\n  ETSY AUTH COMPLETE")
        print(f"  Tokens saved to {TOKENS_FILE.name}")
        print("  Run: python run.py content:etsy\n")
