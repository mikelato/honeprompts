"""
Daily income report -- prints revenue summary and top performers.
Run any time: python run.py content:report
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.db import db_session
from sqlalchemy import text


def run():
    with db_session() as session:
        total = session.execute(
            text("SELECT COALESCE(SUM(amount_usd), 0) FROM income_events WHERE lane='content'")
        ).scalar()

        week = session.execute(
            text("SELECT COALESCE(SUM(amount_usd), 0) FROM income_events WHERE lane='content' AND created_at > NOW() - INTERVAL '7 days'")
        ).scalar()

        month = session.execute(
            text("SELECT COALESCE(SUM(amount_usd), 0) FROM income_events WHERE lane='content' AND created_at > NOW() - INTERVAL '30 days'")
        ).scalar()

        top = session.execute(
            text("""
                SELECT metadata->>'product_name' as product, COUNT(*) as sales, SUM(amount_usd) as revenue
                FROM income_events
                WHERE lane='content' AND event_type IN ('lemon_sale', 'gumroad_sale')
                GROUP BY product
                ORDER BY revenue DESC
                LIMIT 10
            """)
        ).fetchall()

        pins = session.execute(
            text("SELECT COUNT(*) FROM run_log WHERE lane='content' AND action='pinterest_pin' AND created_at > NOW() - INTERVAL '7 days'")
        ).scalar()

        etsy_listings = session.execute(
            text("SELECT COUNT(*) FROM kv_store WHERE lane='content' AND key LIKE 'etsy_listed_%'")
        ).scalar()

        lemon_products = session.execute(
            text("SELECT COUNT(*) FROM kv_store WHERE lane='content' AND key LIKE 'lemon_product_%'")
        ).scalar()

    from pathlib import Path as P
    catalog_size = len(list((P(__file__).resolve().parents[2] / "products").glob("*.pdf")))

    print("\n" + "=" * 55)
    print("   HONE -- INCOME ENGINE REPORT")
    print("=" * 55)
    print(f"  All-time revenue : ${total:,.2f}")
    print(f"  Last 30 days     : ${month:,.2f}")
    print(f"  Last 7 days      : ${week:,.2f}")
    print()
    print(f"  Catalog          : {catalog_size} products")
    print(f"  Lemon Squeezy    : {lemon_products} listed")
    print(f"  Etsy             : {etsy_listings} listed")
    print(f"  Pinterest pins   : {pins} generated (last 7 days)")
    print()
    if top:
        print("  TOP PRODUCTS BY REVENUE")
        for row in top:
            name = (row.product or "Unknown")[:38]
            print(f"    {name:<38} {int(row.sales):>3} sales  ${float(row.revenue):,.2f}")
    else:
        print("  No sales yet -- keep building catalog and pinning.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    run()
