"""
Batch product generator -- runs content:generate N times in sequence.

Run: python run.py content:batch         # default: 5 products
     python run.py content:batch 10      # specify count
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from functions.lane_content.generate_product import run as generate_one


def run(count: int = 5):
    print(f"\n[batch] Generating {count} products...")
    succeeded = 0
    failed = 0

    for i in range(count):
        print(f"\n{'-'*55}")
        print(f"  PRODUCT {i+1} OF {count}")
        print(f"{'-'*55}")
        try:
            generate_one()
            succeeded += 1
        except Exception as e:
            print(f"[batch] Product {i+1} failed: {e}")
            failed += 1
        # Brief pause between runs to avoid hammering the API
        if i < count - 1:
            time.sleep(3)

    print(f"\n{'='*55}")
    print(f"  BATCH COMPLETE: {succeeded} succeeded, {failed} failed")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    run(n)
