# UniCompass — Architecture Benchmark Results

> **Generated:** 2026-04-23 13:59 UTC
> **Endpoint:** `http://localhost:8000/api/feeds/rss?limit=20&active_only=true`
> **Requests per scenario:** 50 measured + 5 warm-up (excluded)
> **Tool:** Custom Python benchmark script (`benchmark.py`)

---

## Experiment Setup

| Parameter | Value |
|---|---|
| Endpoint | `GET /api/feeds/rss?limit=20&active_only=true` |
| Requests per scenario | 50 |
| Warm-up requests | 5 (discarded) |
| Scenario A | Cache-Aside with Redis (TTL = 300 s) |
| Scenario B | Redis flushed before **every** request → true PostgreSQL-only baseline |

---

## Results

| Metric | Scenario A — With Redis Cache | Scenario B — No Cache (DB only) | Improvement |
|---|---|---|---|
| Mean Latency | 3.47 ms | 215.85 ms | **62.2×** |
| p50 Latency | 3.46 ms | 209.12 ms | **60.4×** |
| p95 Latency | 4.31 ms | 294.89 ms | **68.4×** |
| p99 Latency | 4.84 ms | 358.77 ms | **74.1×** |
| Max Latency | 4.84 ms | 358.77 ms | **74.1×** |
| Throughput | 279.96 req/s | 4.59 req/s | **61.0×** |


---

## Analysis

### Performance — Latency (NFR 1)

The Cache-Aside pattern with Redis delivered a ****68.4×** improvement at p95**,
reducing tail latency from 294.89 ms (raw PostgreSQL) to 4.31 ms.
This is significant because the `GET /feed` endpoint is the highest-traffic route in UniCompass
(every user session begins with a feed load). A sub-0-ms p95 ensures
the UI remains responsive even under concurrent load.

### Performance — Throughput (NFR 2)

Redis increased throughput from **4.59 req/s** (PostgreSQL only) to
**279.96 req/s** — an improvement of **61.0×**.
This matters because the feed supports pagination, filtering, and concurrent users; the 5-minute
TTL means a cache hit costs only a Redis network round-trip (~0.1 ms) versus a full SQL query
(table scan + ORM serialisation).

---

## Trade-off Discussion

| Concern | With Redis (Scenario A) | Without Redis (Scenario B) |
|---|---|---|
| **Latency** | Low (cache hit ≈ 1–5 ms) | Higher (DB query ≈ 50–200 ms) |
| **Throughput** | High | Limited by DB connection pool |
| **Data freshness** | Up to 5 min stale | Always fresh |
| **Operational cost** | Redis daemon + memory (~2–5 MB per cache slice) | PostgreSQL only |
| **Complexity** | Invalidation logic in ingestion worker | None |

**Why the trade-off is acceptable for UniCompass:**
- Opportunities are ingested in batches every few minutes — 5-minute staleness is imperceptible to users.
- The ingestion worker explicitly flushes the `feed:*` cache key namespace after each batch, ensuring
  newly ingested data surfaces promptly.
- Redis adds one infrastructure component, but its failure is handled gracefully: the Cache-Aside
  implementation silently falls back to PostgreSQL if Redis is unavailable (see `feeds.py`).

---

## Raw Data

### Scenario A — With Redis Cache
```json
{
  "scenario": "Scenario A \u2014 WITH Redis Cache (Cache-Aside architecture)",
  "n_requests": 50,
  "success": 50,
  "failed": 0,
  "mean_ms": 3.47,
  "min_ms": 2.56,
  "p50_ms": 3.46,
  "p95_ms": 4.31,
  "p99_ms": 4.84,
  "max_ms": 4.84,
  "throughput_rps": 279.96
}
```

### Scenario B — No Cache (PostgreSQL only)
```json
{
  "scenario": "Scenario B \u2014 NO Redis Cache (PostgreSQL direct, flush per request)",
  "n_requests": 50,
  "success": 50,
  "failed": 0,
  "mean_ms": 215.85,
  "min_ms": 201.38,
  "p50_ms": 209.12,
  "p95_ms": 294.89,
  "p99_ms": 358.77,
  "max_ms": 358.77,
  "throughput_rps": 4.59
}
```
