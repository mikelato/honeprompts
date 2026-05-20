"""
Local runner -- loads .env and executes a lane function.

Usage:
    python run.py content:generate            # generate + auto-publish one product (full pipeline)
    python run.py content:batch               # generate 5 products in sequence
    python run.py content:batch 10            # generate N products
    python run.py content:etsy                # list all un-listed products on Etsy
    python run.py content:etsy <slug>         # list a specific product by slug
    python run.py content:etsy-auth           # step 1: get Etsy OAuth URL
    python run.py content:etsy-auth <c> <s>   # step 2: exchange code for tokens
    python run.py content:pin                 # regenerate full Pinterest schedule CSV
    python run.py content:sync                # pull sales from Gumroad + Lemon Squeezy
    python run.py content:report              # print income summary
"""
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

COMMANDS = {
    "content:generate":  "functions.lane_content.generate_product",
    "content:batch":     "functions.lane_content.batch_generate",
    "content:etsy":      "functions.lane_content.publish_to_etsy",
    "content:etsy-auth": "functions.lane_content.etsy_auth",
    "content:pin":       "functions.lane_content.pin_products",
    "content:sync":      "functions.lane_content.sync_sales",
    "content:report":    "functions.lane_content.income_report",
    "content:export":    "functions.lane_content.export_listings",
    "content:website":   "functions.lane_content.update_website",
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python run.py <command> [args]")
        print()
        for cmd in COMMANDS:
            print(f"  {cmd}")
        sys.exit(1)

    cmd = sys.argv[1]
    module_path = COMMANDS[cmd]
    module = __import__(module_path, fromlist=["run"])

    if cmd == "content:batch":
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        module.run(count)
    elif cmd == "content:etsy":
        slug = sys.argv[2] if len(sys.argv) > 2 else None
        module.run(slug)
    elif cmd == "content:etsy-auth":
        code = sys.argv[2] if len(sys.argv) > 2 else None
        state = sys.argv[3] if len(sys.argv) > 3 else None
        module.run(code, state)
    elif cmd == "content:website":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        module.run(domain)
    else:
        module.run()


if __name__ == "__main__":
    main()
