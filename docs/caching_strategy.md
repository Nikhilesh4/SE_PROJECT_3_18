# Redis Caching Strategy — UniCompass

## Overview

This document explains **what** was implemented, **why** each decision was made,
and **which Software Engineering principles** were applied to the Redis caching
layer of the UniCompass application.

---

## Problem Being Solved

Without caching, every user request for the Discovery Feed triggers:
1. A full database query (with sorting + filtering)
2. In-memory filtering for active items (up to 800 rows processed)

For external data ingestion, every worker cycle calls external APIs (Jooble, Adzuna)
even when the data has not changed since the last run. This wears down rate limits and
increases latency.

**Caching solves both problems** by storing pre-computed results so repeated requests
skip the expensive operations entirely.

---

## Architecture Patterns Used

### 1. Cache-Aside Pattern
> *"Check the cache. If it's there, use it. If not, compute it, store it, return it."*

This is the **primary pattern** used across all four caching points.

```
Request
   │
   ▼
[Redis] ──HIT──► Return cached data immediately (fast path)
   │
  MISS
   │
   ▼
[Database / External API]
   │
   ├──► Store result in Redis (with TTL)
   │
   └──► Return result to user
```

**Why Cache-Aside?**
- The data is read much more often than it is written, making it ideal for this pattern.
- If Redis goes down, the application falls back gracefully to the database.
- Cache keys are never "pushed" automatically; the application always controls what is cached.

---

### 2. Decorator Pattern
> *"Wrap a function with extra behavior without changing its code."*

A reusable `@cached` decorator is provided in `app/utils/cache_decorator.py`.
This follows the **Open-Closed Principle**: routes are open for extension (caching)
but closed for modification (their core logic is unchanged).

```python
# Before @cached — reads from DB every single call
def list_rss_opportunities(category, limit, offset, ...):
    return db.query(...)

# After @cached — routes check Redis first; DB only on cache miss
@cached(key_prefix="feed", ttl_seconds=300)
def list_rss_opportunities(category, limit, offset, ...):
    return db.query(...)
```

*(In the implemented code the pattern is applied manually for FastAPI compatibility,
but the `cache_decorator.py` utility is available for future functions.)*

---

### 3. Singleton Pattern
> *"One shared instance of a service, created once and reused everywhere."*

`RedisCacheService` in `app/services/redis_cache.py` is instantiated once
at module level as `redis_cache`. Every part of the application imports this
single object rather than creating new Redis connections.

```python
# Module bottom — instantiated ONCE
redis_cache = RedisCacheService()

# Usage everywhere else
from app.services.redis_cache import redis_cache
redis_cache.get("feed:job:True:50:0")
```

**Why Singleton?**
- Redis connections are expensive to create; reusing one connection pool is efficient.
- Consistent configuration across the entire application.

---

## Architectural Tactics Used

### Tactic 1 — Performance (Response Time Reduction)

| Cache Point | Redis Key Pattern | TTL | Benefit |
|---|---|---|---|
| Discovery Feed | `feed:{category}:{active_only}:{limit}:{offset}` | 5 min | Eliminates DB query on every page load |
| Individual Opportunity | `opportunity:{item_id}` | 30 min | Serves hot items from RAM, preventing DB hotspot |
| User Profile | `profile:{user_id}` | 1 hour | Skips expensive DB read for profile data |
| External API Responses | `source:jooble:{kw}:{loc}:{page}:latest` | 30 min | Prevents duplicate external API calls during worker retries |

---

### Tactic 2 — Availability (Fault Tolerance)

All Redis operations are wrapped in `try/except` inside `RedisCacheService`.
If Redis is unreachable:
- `get()` returns `None` (triggers a cache miss → falls back to DB)
- `set()` returns `False` (result is still returned to the user, just not cached)
- `delete()` returns `False` (a warning is logged; the application continues normally)

**Result:** A Redis outage degrades performance but never crashes the application.

---

### Tactic 3 — Modifiability (Centralized Cache Logic)

All Redis interactions go through the single `RedisCacheService` class.
To change serialization format, key naming conventions, or connection settings,
you edit **one file** (`redis_cache.py`) and the change applies everywhere.

---

### Tactic 4 — Cache Invalidation (Data Consistency)

Stale data is prevented via two invalidation strategies:

**Strategy A — Event-Driven Invalidation (Write-Behind)**
When a worker finishes ingesting new data, it immediately deletes the related cache keys.

```
Ingestion Worker finishes batch
        │
        ▼
redis_cache.delete_pattern("feed:*")   # clears all feed pages
        │
        ▼
Next user request → Cache MISS → Fresh data from DB → Cached again
```

**Strategy B — Targeted Single-Key Invalidation**
When a user uploads a new resume, only their specific profile cache key is deleted.

```
POST /profile/upload-resume (success)
        │
        ▼
redis_cache.delete(f"profile:{user_id}")
        │
        ▼
GET /profile/me → Cache MISS → Fresh profile from DB → Cached again
```

---

## Where Cache is NOT Applied (Design Decisions)

| Endpoint | Reason |
|---|---|
| `POST /auth/login` | JWTs are stateless by design; caching login responses would be a security risk |
| `POST /profile/upload-resume` | One-time operation; result is immediately invalidated anyway |
| Bookmark operations | User-specific writes with high variability and low read frequency |

---

## File-by-File Implementation Summary

### New Files

#### `backend/app/services/redis_cache.py`
Central `RedisCacheService` singleton.
- Methods: `get()`, `set()`, `delete()`, `delete_pattern()`, `is_available()`
- Fault-tolerant: all methods catch exceptions and log warnings instead of crashing.
- Uses lazy connection initialization (Redis is not contacted until first use).

#### `backend/app/utils/cache_decorator.py`
Reusable `@cached` decorator implementing the Cache-Aside pattern.
- Automatically skips SQLAlchemy Session and User objects when building cache keys.
- Supports a custom `key_builder` function for complex key logic.

---

### Modified Files

#### `backend/app/routers/feeds.py`
- `GET /api/feeds/rss` → Cache key: `feed:{category}:{active_only}:{limit}:{offset}`, TTL 5 min
- `GET /api/feeds/rss/{item_id}` → **NEW endpoint** — Cache key: `opportunity:{item_id}`, TTL 30 min

#### `backend/app/routers/profile.py`
- `GET /profile/me` → Cache key: `profile:{user_id}`, TTL 1 hour
- `POST /profile/upload-resume` → Deletes `profile:{user_id}` on success (invalidation)

#### `backend/app/workers/ingestion_worker.py`
- After each ingestion batch: `redis_cache.delete_pattern("feed:*")` to wipe all feed pages.

#### `backend/app/workers/rss_refresh_worker.py`
- After each category refresh: `redis_cache.delete_pattern(f"feed:{category}:*")` for targeted invalidation.

#### `backend/app/services/adapters/jooble_adapter.py`
- `fetch_opportunities()` → Checks `source:jooble:{kw}:{loc}:{page}:latest` before calling the Jooble API.
- Caches raw API JSON responses for 30 min to prevent redundant external calls.

---

## Redis Key Reference

| Key Pattern | TTL | Set By | Deleted By |
|---|---|---|---|
| `feed:{cat}:{active}:{limit}:{offset}` | 300s (5m) | `feeds.py` router | Ingestion worker, RSS worker |
| `opportunity:{item_id}` | 1800s (30m) | `feeds.py` router | Expires naturally |
| `profile:{user_id}` | 3600s (1h) | `profile.py` router | Resume upload endpoint |
| `source:jooble:{kw}:{loc}:{page}:latest` | 1800s (30m) | `jooble_adapter.py` | Expires naturally |
| `rss:last_refresh:{category}` | No TTL | Existing `cache_service.py` | Existing logic (not changed) |

---

## How to Verify the Caching is Working

Run this in a terminal while the app is running:

```bash
# Connect to Redis and watch all commands in real time
docker exec -it unicompass-redis redis-cli monitor
```

Then open the app in your browser and navigate to the **Discovery Feed**.
You will see lines like:
```
"SET" "feed:None:True:50:0" "..." "EX" "300"   ← First visit (MISS → store)
"GET" "feed:None:True:50:0"                      ← Second visit (HIT → instant)
```

To check the TTL of a specific key:
```bash
docker exec -it unicompass-redis redis-cli TTL "feed:None:True:50:0"
# Returns: 287  (seconds remaining)
```
