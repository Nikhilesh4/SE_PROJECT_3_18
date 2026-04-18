# Architectural Tactics — UniCompass

> **Project:** UniCompass — AI-powered opportunity discovery platform
> **Date:** 2026-04-18

---

## Overview

Architectural tactics are design decisions that directly address specific non-functional requirements (NFRs). Each tactic below is implemented in the current codebase and linked to the quality attribute it satisfies.

---

## Tactic 1: Per-Category Content Filtering (Data Quality)

**NFR addressed:** Data Quality / Relevance

**Problem:** RSS feeds and APIs return a mix of real opportunities and irrelevant content — blog articles, tutorials, news recaps, experience posts, visa guides, and opinion pieces. Showing these degrades user trust.

**Tactic:** Apply a **multi-layer, per-category content filter** at three pipeline stages: ingestion (write path), aggregation (live fetch), and cache read (DB read path). Each category has its own pattern sets:

- **Hackathon** — strict two-signal model: requires BOTH an action word (register, apply, deadline) AND an event word (hackathon, competition, prize). Hard-rejects past events, experience posts, and news.
- **Internship** — requires internship-specific signals (intern, co-op, trainee, entry-level, fresher, stipend). Rejects generic job listings.
- **Research** — requires academic opportunity signals (PhD, postdoc, fellowship, lab opening, grant). Rejects visa guides, study-abroad blogs, and test prep articles.
- **Job/Freelance** — rejects career-advice articles and how-to guides.

**Implementation:** `services/rss/filter.py` → `is_opportunity_post()` called in `cache_service.py`, `aggregator.py`, and `rss_refresh_worker.py`.

**Trade-off:** Aggressive filtering may occasionally reject legitimate opportunities whose titles resemble blog articles. This is acceptable because false negatives (missing one opportunity) are less harmful than false positives (showing irrelevant content).

---

## Tactic 2: Caching with TTL-Based Staleness (Performance)

**NFR addressed:** Performance / Responsiveness

**Problem:** Fetching from 20+ external RSS feeds and APIs on every user request would cause multi-second response times and overwhelm external rate limits.

**Tactic:** Use a **two-tier caching strategy**:

1. **Redis TTL timestamps** — Each category has a configurable TTL (e.g., jobs: 30 min, hackathons: 60 min). The background worker only fetches from external sources when a category's cache is stale.
2. **PostgreSQL as the read cache** — All API requests read from the local DB, never from external sources directly. The DB acts as a warm cache refreshed by the background worker.

**Implementation:** `services/rss/cache_service.py` (staleness checks via Redis), `services/rss/refresh_strategy.py` (TTL configuration per category), `workers/rss_refresh_worker.py` (periodic refresh loop).

**Trade-off:** Data may be up to TTL-minutes stale. This is acceptable for opportunity listings which don't change minute-by-minute. A manual refresh endpoint (`POST /feeds/rss/refresh`) allows immediate refresh when needed.

---

## Tactic 3: Idempotent Ingestion via Upsert (Reliability)

**NFR addressed:** Reliability / Fault Recovery / Data Integrity

**Problem:** The ingestion worker runs on a timer, on startup, and can be triggered manually. The same items will be fetched repeatedly. Without idempotency, this would cause duplicate rows, broken pagination, and inflated counts.

**Tactic:** Use PostgreSQL's `INSERT ... ON CONFLICT (guid) DO UPDATE` (upsert). Every write operation is idempotent — running it N times produces the same result as running it once.

- **On conflict:** Only volatile fields (title, summary, tags, published_at, updated_at) are refreshed.
- **Preserved fields:** `guid`, `url`, and `created_at` are never overwritten — the first-seen timestamp is permanent.
- **Batch dedup:** Within-batch deduplication prevents `CardinalityViolation` when the same guid appears twice in one INSERT.

**Implementation:** `repositories/rss_repository.py` → `upsert_items()` using `sqlalchemy.dialects.postgresql.insert`.

**Trade-off:** `rowcount` includes both inserts and updates, so we cannot distinguish "new" from "refreshed" items without additional SELECT queries.

---

## Tactic 4: Fault Isolation via Adapter Pattern (Availability)

**NFR addressed:** Availability / Fault Tolerance

**Problem:** External data sources fail unpredictably — DNS timeouts, 403 errors, rate limiting, schema changes. A single source failure should not bring down the entire ingestion pipeline.

**Tactic:** Each data source is wrapped in an independent adapter with its own **try/except** boundary. The `AggregatorFacade` iterates over all adapters and catches exceptions per-adapter. A failing adapter is logged and skipped; all other adapters continue.

```python
for adapter in self._adapters:
    try:
        items = self._fetch_from_adapter(adapter)
        self._dedup_extend(merged, seen_urls, items)
    except Exception as exc:
        logger.error("Adapter %s failed: %s", adapter.__class__.__name__, exc)
        # Pipeline continues with remaining adapters
```

**Implementation:** `services/adapters/aggregator_facade.py`, `services/adapters/base_adapter.py`, individual adapters (`adzuna_adapter.py`, `jooble_adapter.py`).

**Trade-off:** Failed adapters contribute zero items for that cycle, so the feed may have fewer results. This is acceptable because partial data is better than no data or a crashed pipeline.

---

## Tactic 5: Async Offloading via Thread Pool (Responsiveness)

**NFR addressed:** Responsiveness / Concurrent Request Handling

**Problem:** The ingestion pipeline makes 20+ synchronous HTTP calls (each up to 25s timeout). Running these in the FastAPI async event loop would block all concurrent API requests for the duration.

**Tactic:** Offload the synchronous `AggregatorFacade.fetch_all_opportunities()` call to a **thread-pool executor** using `asyncio.get_running_loop().run_in_executor()`. The event loop remains free to serve API requests while ingestion runs in a background thread.

**Implementation:** `workers/ingestion_worker.py` → `_run_ingestion_cycle()`.

**Trade-off:** Uses a thread from Python's default ThreadPoolExecutor. Long-running cycles consume a thread for minutes. This is acceptable at current scale (single worker, 30-min cycle).

---

## Summary Matrix

| # | Tactic | Primary NFR | Secondary NFR | Key File |
|---|--------|------------|---------------|----------|
| 1 | Per-category content filtering | Data Quality | Usability | `filter.py` |
| 2 | TTL-based caching | Performance | Scalability | `cache_service.py`, `refresh_strategy.py` |
| 3 | Idempotent upsert | Reliability | Data Integrity | `rss_repository.py` |
| 4 | Fault-isolated adapters | Availability | Fault Tolerance | `aggregator_facade.py` |
| 5 | Async offloading | Responsiveness | Throughput | `ingestion_worker.py` |
