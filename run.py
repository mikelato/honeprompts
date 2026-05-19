"""
Local runner — loads .env and executes a lane function.

Usage:
    python run.py content:generate   # Claude designs + publishes a product to Gumroad
    python run.py content:etsy       # List latest Gumroad product on Etsy
    python run.py content:pin        # Create Pinterest pins for all live products
    python run.py content:sync       # Pull Gumroad sales into DB
    python run.py content:report     # Print income summary
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

COMMANDS = {
    "content:generate": "functions.lane_content.generate_product",
    "content:etsy":     "functions.lane_content.publish_to_etsy",
    "content:pin":      "functions.lane_content.pin_products",
    "content:sync":     "functions.lane_content.sync_sales",
    "content:report":   "functions.lane_content.income_report",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python run.py <command>")
        print()
        for cmd in COMMANDS:
            print(f"  {cmd}")
        sys.exit(1)

    module_path = COMMANDS[sys.argv[1]]
    module = __import__(module_path, fromlist=["run"])
    module.run()


if __name__ == "__main__":
    main()
