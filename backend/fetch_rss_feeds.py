#!/usr/bin/env python3
"""
CLI: fetch all configured RSS feeds, normalize to the common schema, print a report.

Run from the backend directory (same as uvicorn):

    cd SE_PROJECT_3_18/backend
    ./venv/bin/python fetch_rss_feeds.py
    ./venv/bin/python fetch_rss_feeds.py --limit 5 --category job
"""

from __future__ import annotations

import argparse
from textwrap import shorten

from app.services.rss import aggregate_all_feeds


def main() -> None:
    p = argparse.ArgumentParser(description="Fetch and display UniCompass RSS ingestion.")
    p.add_argument("--limit", type=int, default=8, help="Max items per feed (default 8)")
    p.add_argument(
        "--category",
        type=str,
        default=None,
        help="Only sources in this category (e.g. internship, job, freelance)",
    )
    p.add_argument("--sources-only", action="store_true", help="Print source status, skip item lines")
    args = p.parse_args()

    result = aggregate_all_feeds(
        limit_per_feed=args.limit,
        category_filter=args.category,
    )

    print("\n" + "=" * 88)
    print("UniCompass RSS aggregation")
    print(f"  Fetched at (UTC): {result.fetched_at.isoformat()}")
    print(f"  Total normalized items: {result.total_items}")
    print("=" * 88)

    print("\n--- Per-source status ---")
    for s in result.sources:
        flag = "OK " if s.ok else "ERR"
        extra = f"  ({s.error})" if s.error else ""
        print(
            f"  [{flag}] {s.category:12s} {s.source_name[:40]:40s} "
            f"http={str(s.http_status):>4s} entries={s.entries_fetched:>3d} "
            f"normalized={s.items_normalized:>3d}{extra}"
        )

    if args.sources_only:
        return

    print("\n--- Items (title / source / category / url) ---")
    for i, it in enumerate(result.items, 1):
        title = shorten(it.title, width=72, placeholder="…")
        pub = it.published_at.isoformat()[:19] if it.published_at else "—"
        print(f"\n  [{i:4d}] [{it.category}] {it.source_name}")
        print(f"         {title}")
        print(f"         {pub}  {it.url}")
        if it.summary:
            print(f"         {shorten(it.summary, width=100, placeholder='…')}")


if __name__ == "__main__":
    main()
