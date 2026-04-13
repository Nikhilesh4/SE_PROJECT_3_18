#!/usr/bin/env python3
"""
RSS Feed Explorer — Test and discover feeds for the UniCompass pipeline.

Usage:
    python explore_feeds.py                   # Run all tests
    python explore_feeds.py --native          # Test only native RSS feeds
    python explore_feeds.py --bridge          # Test only RSS-Bridge feeds
    python explore_feeds.py --url <feed_url>  # Test a single custom URL
"""

import feedparser
import urllib.request
import json
import sys
import time
from textwrap import shorten

# ============================================================
# CONFIGURATION
# ============================================================

RSS_BRIDGE_URL = "http://localhost:3000"

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) UniCompass/1.0"}

# ============================================================
# SECTION 1: Native RSS Feeds (no RSS-Bridge needed)
# ============================================================

NATIVE_FEEDS = {
    # --- Hackathons / Competitions ---
    "DevPost Hackathons":       "https://devpost.com/hackathons.atom",
    "MLContests":               "https://mlcontests.com/rss",
    "HackerEarth Challenges":   "https://www.hackerearth.com/challenges/feed/",

    # --- Remote Jobs ---
    "RemoteOK":                 "https://remoteok.com/remote-jobs.rss",
    "WeWorkRemotely":           "https://weworkremotely.com/categories/remote-programming-jobs.rss",

    # --- Filtered HackerNews (via hnrss.org) ---
    "HN: Hackathons":          "https://hnrss.org/newest?q=hackathon",
    "HN: Internships":         "https://hnrss.org/newest?q=internship",
    "HN: Scholarships":        "https://hnrss.org/newest?q=scholarship",

    # --- Research ---
    "arXiv CS.AI (recent)":    "http://export.arxiv.org/rss/cs.AI",
}

# ============================================================
# SECTION 2: RSS-Bridge Feeds (requires RSS-Bridge running)
# ============================================================

def bridge_url(bridge: str, params: dict, fmt: str = "Atom") -> str:
    """Build an RSS-Bridge URL."""
    query = "&".join(f"{k}={v.replace(' ', '+')}" for k, v in params.items())
    return f"{RSS_BRIDGE_URL}/?action=display&bridge={bridge}&format={fmt}&{query}"

RSS_BRIDGE_FEEDS = {
    "LinkedIn (software intern)": lambda: bridge_url(
        "LinkedInSearchBridge", {"keywords": "software intern", "limit": "5"}
    ),
    "GitHub Trending":            lambda: bridge_url(
        "GitHubTrendingBridge", {"language": "python", "date_range": "today"}
    ),
    "Reddit r/internships":       lambda: bridge_url(
        "RedditBridge", {"context": "internships", "score": "10"}
    ),
    "Twitter/X #hackathon":       lambda: bridge_url(
        "XBridge", {"q": "#hackathon", "norep": "on"}
    ),
    "YouTube CS Opportunities":   lambda: bridge_url(
        "YoutubeBridge", {"s": "computer science internship 2026", "type": "keyword"}
    ),
}

# ============================================================
# HELPERS
# ============================================================

def fetch_feed(url: str) -> feedparser.FeedParserDict:
    """Fetch and parse a feed, adding a User-Agent header."""
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        raw = urllib.request.urlopen(req, timeout=15).read()
        return feedparser.parse(raw)
    except Exception as e:
        # fallback: let feedparser try directly
        feed = feedparser.parse(url)
        feed._fetch_error = str(e)
        return feed


def print_header(text: str, char: str = "="):
    width = 70
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def print_feed_report(name: str, url: str, feed: feedparser.FeedParserDict):
    """Pretty-print everything useful about a parsed feed."""
    status = getattr(feed, 'status', '?')
    bozo = feed.bozo

    print(f"\n  📡 {name}")
    print(f"     URL:     {shorten(url, 80)}")
    print(f"     Status:  {status}  |  Bozo (parse error): {bozo}")

    if bozo:
        print(f"     ⚠️  Error: {feed.bozo_exception}")

    if hasattr(feed, '_fetch_error'):
        print(f"     ⚠️  Fetch error: {feed._fetch_error}")

    # Feed metadata
    ft = feed.feed.get("title", "—")
    fl = feed.feed.get("link", "—")
    print(f"     Title:   {ft}")
    print(f"     Link:    {fl}")
    print(f"     Entries: {len(feed.entries)}")

    if not feed.entries:
        print(f"     ❌ No entries. Feed may be dead, blocked, or empty.")
        return

    # === Show available fields ===
    first = feed.entries[0]
    print(f"\n     📋 Available fields in entries:")
    for key in sorted(first.keys()):
        val = str(first[key])[:60].replace("\n", " ")
        print(f"        • {key:22s} = {val}")

    # === Preview first 3 entries ===
    print(f"\n     📰 Preview (first 3 entries):")
    for i, entry in enumerate(feed.entries[:3]):
        title = entry.get("title", "No title")
        link = entry.get("link", "—")
        pub = entry.get("published", entry.get("updated", "—"))
        summary = entry.get("summary", entry.get("description", ""))
        summary_short = shorten(summary.replace("\n", " "), 100, placeholder="...")

        print(f"\n     [{i+1}] {shorten(title, 70)}")
        print(f"         🔗 {link}")
        print(f"         📅 {pub}")
        if summary_short:
            print(f"         📝 {summary_short}")

    # === Mapping suggestion ===
    print(f"\n     🗺️  Suggested OpportunityCard mapping:")
    mappings = {
        "title":       next((k for k in ["title"] if k in first), None),
        "source_url":  next((k for k in ["link", "id"] if k in first), None),
        "description": next((k for k in ["summary", "description", "content"] if k in first), None),
        "published":   next((k for k in ["published", "updated", "pubDate"] if k in first), None),
        "tags":        next((k for k in ["tags", "categories", "category"] if k in first), None),
    }
    for card_field, feed_field in mappings.items():
        status = f"entry.{feed_field}" if feed_field else "❌ NOT FOUND"
        print(f"        card.{card_field:15s} ← {status}")


def check_rss_bridge_alive() -> bool:
    """Check if RSS-Bridge container is running."""
    try:
        req = urllib.request.Request(RSS_BRIDGE_URL, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


# ============================================================
# MAIN
# ============================================================

def test_native_feeds():
    print_header("SECTION 1: Native RSS Feeds (no RSS-Bridge needed)")
    results = {"alive": [], "dead": []}

    for name, url in NATIVE_FEEDS.items():
        feed = fetch_feed(url)
        print_feed_report(name, url, feed)

        if feed.entries:
            results["alive"].append(name)
        else:
            results["dead"].append(name)

    # Summary
    print_header("Native Feeds Summary", "-")
    print(f"  ✅ Working ({len(results['alive'])}): {', '.join(results['alive']) or 'none'}")
    print(f"  ❌ Dead/Blocked ({len(results['dead'])}): {', '.join(results['dead']) or 'none'}")


def test_bridge_feeds():
    print_header("SECTION 2: RSS-Bridge Feeds")

    if not check_rss_bridge_alive():
        print(f"\n  ❌ RSS-Bridge is NOT running at {RSS_BRIDGE_URL}")
        print(f"  Start it with: docker compose up -d rss-bridge")
        print(f"  Then re-run:   python explore_feeds.py --bridge")
        return

    print(f"  ✅ RSS-Bridge is running at {RSS_BRIDGE_URL}")

    for name, url_fn in RSS_BRIDGE_FEEDS.items():
        url = url_fn()
        feed = fetch_feed(url)
        print_feed_report(name, url, feed)


def test_single_url(url: str):
    print_header(f"Testing single URL")
    feed = fetch_feed(url)
    print_feed_report("Custom Feed", url, feed)


def list_bridge_bridges():
    """Fetch and display available bridges from RSS-Bridge."""
    print_header("Available RSS-Bridge Bridges")

    if not check_rss_bridge_alive():
        print(f"\n  ❌ RSS-Bridge is NOT running at {RSS_BRIDGE_URL}")
        return

    list_url = f"{RSS_BRIDGE_URL}/?action=list&format=json"
    try:
        req = urllib.request.Request(list_url, headers=HEADERS)
        raw = urllib.request.urlopen(req, timeout=10).read()
        # Depending on RSS-Bridge version, this may or may not work
        bridges = json.loads(raw)
        print(f"\n  Total bridges available: {len(bridges)}")
        print(f"\n  Some interesting ones for opportunities:")
        keywords = ["linkedin", "github", "reddit", "kaggle", "indeed",
                     "glassdoor", "intern", "job", "scholar", "youtube"]
        for b_name, b_info in sorted(bridges.items()):
            name_lower = b_name.lower()
            if any(kw in name_lower for kw in keywords):
                desc = b_info.get("description", "")[:60] if isinstance(b_info, dict) else ""
                print(f"    • {b_name:30s}  {desc}")
    except Exception as e:
        print(f"\n  ⚠️  Could not list bridges via API: {e}")
        print(f"  → Visit {RSS_BRIDGE_URL} in your browser to see the full list")


if __name__ == "__main__":
    args = sys.argv[1:]

    if "--url" in args:
        idx = args.index("--url")
        if idx + 1 < len(args):
            test_single_url(args[idx + 1])
        else:
            print("Usage: python explore_feeds.py --url <feed_url>")
    elif "--native" in args:
        test_native_feeds()
    elif "--bridge" in args:
        test_bridge_feeds()
    elif "--list-bridges" in args:
        list_bridge_bridges()
    else:
        # Run everything
        test_native_feeds()
        print("\n")
        test_bridge_feeds()
        print("\n")
        list_bridge_bridges()

    print(f"\n{'='*70}")
    print(f"  Done! Use the field mappings above to build your RSSAdapter.")
    print(f"{'='*70}\n")
