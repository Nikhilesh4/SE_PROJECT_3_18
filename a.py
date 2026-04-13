# a.py
import feedparser
import requests
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

@dataclass
class OpportunityCard:
    title: str
    url: str
    source: str
    category: str
    description: str
    company: Optional[str]
    location: Optional[str]
    published_at: Optional[datetime]
    tags: list[str]

def map_remoteok(entry) -> OpportunityCard:
    return OpportunityCard(
        title        = entry.get("title", ""),
        url          = entry.get("link", ""),
        source       = "remoteok",
        category     = "internship",
        description  = entry.get("summary", ""),
        company      = entry.get("company"),
        location     = entry.get("location"),
        published_at = _parse_date(entry),
        tags         = [t["term"] for t in entry.get("tags", [])]
    )

def map_weworkremotely(entry) -> OpportunityCard:
    raw_title = entry.get("title", "")
    parts     = raw_title.split(":", 1)
    company   = parts[0].strip() if len(parts) == 2 else None
    title     = parts[1].strip() if len(parts) == 2 else raw_title
    return OpportunityCard(
        title        = title,
        url          = entry.get("link", ""),
        source       = "weworkremotely",
        category     = "internship",
        description  = entry.get("summary", ""),
        company      = company,
        location     = "Remote",
        published_at = _parse_date(entry),
        tags         = [t["term"] for t in entry.get("tags", [])]
    )

def map_arxiv(entry) -> OpportunityCard:
    return OpportunityCard(
        title        = entry.get("title", ""),
        url          = entry.get("link", ""),
        source       = "arxiv",
        category     = "research",
        description  = entry.get("summary", ""),
        company      = None,
        location     = None,
        published_at = _parse_date(entry),
        tags         = [t["term"] for t in entry.get("tags", [])]
    )

def map_hackernews_jobs(entry) -> OpportunityCard:
    return OpportunityCard(
        title        = entry.get("title", ""),
        url          = entry.get("link", ""),
        source       = "hackernews",
        category     = "internship",
        description  = entry.get("summary", ""),
        company      = None,
        location     = None,
        published_at = _parse_date(entry),
        tags         = []
    )

def _parse_date(entry) -> Optional[datetime]:
    parsed = entry.get("published_parsed")
    if parsed:
        return datetime(*parsed[:6])
    return None

FEED_CONFIG = [
    ("https://remoteok.com/remote-jobs.rss",                                map_remoteok),
    ("https://remoteok.com/remote-internship-jobs.rss",                     map_remoteok),
    ("https://weworkremotely.com/remote-jobs.rss",                          map_weworkremotely),
    ("https://weworkremotely.com/categories/remote-programming-jobs.rss",   map_weworkremotely),
    ("https://hnrss.org/jobs",                                              map_hackernews_jobs),
    ("https://export.arxiv.org/rss/cs.AI",                                  map_arxiv),
]

class RSSAdapter:
    def fetch(self) -> list[OpportunityCard]:
        results = []
        for url, mapper in FEED_CONFIG:
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                if r.status_code != 200:
                    print(f"[SKIP] {url} → HTTP {r.status_code}")
                    continue
                feed = feedparser.parse(r.content)
                for entry in feed.entries:
                    results.append(mapper(entry))
                print(f"[OK]   {url} → {len(feed.entries)} entries fetched")
            except Exception as e:
                print(f"[ERR]  {url} → {e}")
        return results


# ✅ THIS IS WHAT WAS MISSING — actually run it
if __name__ == "__main__":
    print("Starting RSS ingestion...\n")
    adapter = RSSAdapter()
    opportunities = adapter.fetch()

    print(f"\n{'='*50}")
    print(f"Total opportunities fetched: {len(opportunities)}")
    print(f"{'='*50}\n")

    # Print first 5 as a preview
    for opp in opportunities[:5]:
        print(f"Title   : {opp.title}")
        print(f"Source  : {opp.source} | Category: {opp.category}")
        print(f"Company : {opp.company}")
        print(f"Location: {opp.location}")
        print(f"URL     : {opp.url}")
        print(f"Tags    : {opp.tags[:4]}")
        print(f"Date    : {opp.published_at}")
        print("-" * 50)