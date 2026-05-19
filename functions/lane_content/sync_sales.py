"""
Pull Gumroad sales and write them to income_events in PostgreSQL.
Run on a schedule (every 15 min) to keep the DB current.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.db import db_session, log_income_event
from shared.gumroad_client import get_sales


def run():
    sales = get_sales()
    new_count = 0
    with db_session() as session:
        for sale in sales:
            # Idempotent: skip if already logged
            from sqlalchemy import text
            exists = session.execute(
                text("SELECT 1 FROM income_events WHERE metadata->>'gumroad_sale_id' = :sid LIMIT 1"),
                {"sid": sale["id"]},
            ).fetchone()
            if exists:
                continue
            log_income_event(
                session=session,
                lane="content",
                event_type="gumroad_sale",
                amount_usd=float(sale.get("price", 0)) / 100,
                metadata={
                    "gumroad_sale_id": sale["id"],
                    "product_name": sale.get("product_name"),
                    "buyer_email": sale.get("email"),
                    "created_at": sale.get("created_at"),
                },
            )
            new_count += 1
    print(f"[sync_sales] Logged {new_count} new sale(s).")


if __name__ == "__main__":
    run()
