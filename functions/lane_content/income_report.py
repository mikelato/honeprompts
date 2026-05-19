"""
Daily income report — prints revenue summary and top performers.
Run any time: python run.py content:report
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from shared.db import db_session
from sqlalchemy import text


def run():
    with db_session() as session:
        # Total all-time
        total = session.execute(
            text("SELECT COALESCE(SUM(amount_usd), 0) FROM income_events WHERE lane='content'")
        ).scalar()

        # Last 7 days
        week = session.execute(
            text("SELECT COALESCE(SUM(amount_usd), 0) FROM income_events WHERE lane='content' AND created_at > NOW() - INTERVAL '7 days'")
        ).scalar()

        # Last 30 days
        month = session.execute(
            text("SELECT COALESCE(SUM(amount_usd), 0) FROM income_events WHERE lane='content' AND created_at > NOW() - INTERVAL '30 days'")
        ).scalar()

        # Top products (by revenue)
        top = session.execute(
            text("""
                SELECT metadata->>'product_name' as product, COUNT(*) as sales, SUM(amount_usd) as revenue
                FROM income_events
                WHERE lane='content' AND event_type='gumroad_sale'
                GROUP BY product
                ORDER BY revenue DESC
                LIMIT 5
            """)
        ).fetchall()

        # Pin count this week
        pins = session.execute(
            text("SELECT COUNT(*) FROM run_log WHERE lane='content' AND action='pinterest_pin' AND created_at > NOW() - INTERVAL '7 days'")
        ).scalar()

    print("\n" + "=" * 50)
    print("   AI INCOME ENGINE — CONTENT LANE REPORT")
    print("=" * 50)
    print(f"  All-time revenue : ${total:,.2f}")
    print(f"  Last 30 days     : ${month:,.2f}")
    print(f"  Last 7 days      : ${week:,.2f}")
    print(f"  Pinterest pins   : {pins} (last 7 days)")
    print()
    if top:
        print("  TOP PRODUCTS")
        for row in top:
            print(f"    {row.product:<35} {row.sales:>3} sales  ${row.revenue:,.2f}")
    else:
        print("  No sales yet — keep building catalog and pinning.")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    run()
