"""
Local runner — loads .env and executes a lane function.

Usage:
    python run.py content:generate   # generate + publish a new product
    python run.py content:sync       # pull Gumroad sales into DB
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def main():
    if len(sys.argv) < 2:
        print("Usage: python run.py <lane>:<command>")
        print("  content:generate  — generate and publish a digital product")
        print("  content:sync      — sync Gumroad sales to DB")
        sys.exit(1)

    target = sys.argv[1]

    if target == "content:generate":
        from functions.lane_content.generate_product import run
    elif target == "content:sync":
        from functions.lane_content.sync_sales import run
    else:
        print(f"Unknown target: {target}")
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
