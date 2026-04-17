"""
Standalone smoke test for AdzunaAdapter.
No database, no Redis, no pytest required.

Usage (from backend/):
    source venv/bin/activate
    python test_adzuna.py
"""

import sys
import os

# Make sure the app package is importable from the backend root
sys.path.insert(0, os.path.dirname(__file__))

# Load .env before importing settings
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env.local"))
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

from app.services.rss.adzuna_adapter import AdzunaAdapter  # noqa: E402


def main() -> None:
    adapter = AdzunaAdapter()

    print("=" * 60)
    print("AdzunaAdapter smoke test")
    print("=" * 60)

    # --- Single fetch ---
    print("\n[1] fetch(keywords='python internship', country='gb', results_per_page=5)")
    items = adapter.fetch(
        keywords="python internship",
        country="gb",
        results_per_page=5,
        category="internship",
    )
    print(f"    → {len(items)} items returned")
    for i, item in enumerate(items, 1):
        print(f"    [{i}] {item.title[:80]!r}")
        print(f"         url     : {item.url[:70]}")
        print(f"         category: {item.category}")
        print(f"         guid    : {item.guid}")

    # --- fetch_for_category ---
    print("\n[2] fetch_for_category('job')")
    job_items = adapter.fetch_for_category("job", results_per_page=3)
    print(f"    → {len(job_items)} items returned")

    # --- unsupported category ---
    print("\n[3] fetch_for_category('hackathon') — expects empty list (not supported)")
    hack_items = adapter.fetch_for_category("hackathon", results_per_page=5)
    print(f"    → {len(hack_items)} items (expected 0)")

    # --- fetch_all ---
    print("\n[4] fetch_all(results_per_page=5)")
    all_items = adapter.fetch_all(results_per_page=5)
    print(f"    → {len(all_items)} unique items across all categories")

    print("\n" + "=" * 60)
    if items or job_items or all_items:
        print("✓ AdzunaAdapter is working correctly.")
    else:
        print("⚠  No items returned — ensure ADZUNA_APP_ID and ADZUNA_APP_KEY are set in .env")
    print("=" * 60)


if __name__ == "__main__":
    main()
