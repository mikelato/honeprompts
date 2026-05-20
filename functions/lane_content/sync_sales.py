"""
Pull sales from all configured storefronts (Gumroad, Lemon Squeezy)
and write them to income_events in PostgreSQL.
Run on a schedule (every 15 min) to keep the DB current.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.db import db_session, log_income_event
from sqlalchemy import text


def _sync_gumroad(session):
    token = os.environ.get("GUMROAD_ACCESS_TOKEN", "")
    if not token or token.startswith("..."):
        return 0

    from shared.gumroad_client import get_sales
    sales = get_sales()
    count = 0
    for sale in sales:
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
        count += 1
    return count


def _sync_lemon(session):
    key = os.environ.get("LEMON_API_KEY", "")
    if not key or key.startswith("..."):
        return 0

    from shared.lemon_client import get_orders, get_store_id
    store_id = get_store_id()
    orders = get_orders(store_id=store_id)
    count = 0
    for order in orders:
        attrs = order.get("attributes", {})
        if attrs.get("status") != "paid":
            continue
        order_id = str(order["id"])
        exists = session.execute(
            text("SELECT 1 FROM income_events WHERE metadata->>'lemon_order_id' = :oid LIMIT 1"),
            {"oid": order_id},
        ).fetchone()
        if exists:
            continue
        amount_usd = attrs.get("total", 0) / 100
        product_name = (attrs.get("first_order_item") or {}).get("product_name", "Unknown")
        log_income_event(
            session=session,
            lane="content",
            event_type="lemon_sale",
            amount_usd=amount_usd,
            metadata={
                "lemon_order_id": order_id,
                "product_name": product_name,
                "buyer_email": attrs.get("user_email"),
                "order_number": attrs.get("order_number"),
                "created_at": attrs.get("created_at"),
            },
        )
        count += 1
    return count


def run():
    with db_session() as session:
        gumroad_count = _sync_gumroad(session)
        lemon_count = _sync_lemon(session)

    total = gumroad_count + lemon_count
    if gumroad_count:
        print(f"[sync_sales] Gumroad: {gumroad_count} new sale(s)")
    if lemon_count:
        print(f"[sync_sales] Lemon Squeezy: {lemon_count} new sale(s)")
    if not total:
        print("[sync_sales] No new sales.")


if __name__ == "__main__":
    run()
