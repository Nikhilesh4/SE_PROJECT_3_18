# Architecture Decision Records — AggregatorFacade & Ingestion Pipeline

> **Project:** UniCompass — AI-powered opportunity discovery platform
> **Component:** RSS/API ingestion subsystem
> **Date:** 2026-04-18
> **Status:** Accepted

---

## Table of Contents

| # | Title |
|---|-------|
| [ADR-001](#adr-001) | Facade over direct adapter calls |
| [ADR-002](#adr-002) | Adapter pattern for external data sources |
| [ADR-003](#adr-003) | Two-layer deduplication (in-memory + DB) |
| [ADR-004](#adr-004) | Async offloading via `run_in_executor` |
| [ADR-005](#adr-005) | Idempotent upsert with `ON CONFLICT DO UPDATE` |
| [ADR-006](#adr-006) | Repository pattern for data access |
| [ADR-007](#adr-007) | Background loop via FastAPI lifespan + asyncio |

---

## ADR-001 — Facade over direct adapter calls {#adr-001}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

The ingestion pipeline must pull data from three heterogeneous sources: an RSS feed aggregator, the Adzuna REST API, and the Jooble REST API. Each has a different client interface, authentication scheme, and response shape. Without a unifying layer, every consumer (the background worker, any future admin endpoint) would need to know about each source individually.

### Decision

Introduce `AggregatorFacade` as a **Facade** (GoF) that exposes exactly one method — `fetch_all_opportunities()` — and delegates to all registered adapters internally.

```python
# Before (hypothetical direct calls)
rss_items   = aggregate_all_feeds(limit_per_feed=50).items
adzuna_items = AdzunaAdapter().fetch_all()
jooble_items = JoobleAdapter().fetch_all_default_queries()
all_items = deduplicate(rss_items + adzuna_items + jooble_items)

# After (one call)
all_items = AggregatorFacade().fetch_all_opportunities()
```

### Rationale

- **Single responsibility:** The worker and API endpoints focus on scheduling/serving; the facade owns source orchestration.
- **Extensibility:** Adding a new source (e.g., LinkedIn) requires only a new adapter subclass and registration — zero changes to callers.
- **Testability:** The entire aggregation chain can be tested through one entry point; callers can be tested with a stub facade.

### Consequences

- All callers are shielded from adapter implementation details.
- The facade becomes a choke point — if it fails unexpectedly (outside per-adapter isolation) all sources fail together. This is mitigated by ADR-003 fault isolation.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Direct adapter calls in the worker | Leaks adapter knowledge into the worker; adding a source breaks the worker |
| Event-driven (publish/subscribe) | Over-engineering for current scale; adds queue infrastructure complexity |

---

## ADR-002 — Adapter pattern for external data sources {#adr-002}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

Every external data source (Adzuna, Jooble, future providers) has a different API contract, authentication mechanism, response schema, and error model. Binding the pipeline to any specific provider's interface would make swapping or adding sources expensive.

### Decision

Define an abstract base class `OpportunityAdapter` (Adapter pattern) that every source driver implements. All adapters translate their source's native format into the shared `NormalizedRssItem` schema.

```python
class OpportunityAdapter(ABC):
    @abstractmethod
    def fetch_opportunities(self, *, keywords, location, page, limit) -> list[NormalizedRssItem]:
        ...
```

### Rationale

- **Interoperability:** The rest of the pipeline only ever sees `NormalizedRssItem`s — it is completely decoupled from provider-specific DTOs.
- **Substitutability (Liskov):** Any `OpportunityAdapter` subclass can be passed to the facade without changing the facade code.
- **Parallel development:** Team members can work on new adapters independently without touching shared pipeline code.

### Consequences

- New adapters must conform to the `fetch_opportunities` signature.
- Adapters with richer multi-query methods (Jooble) expose those as _additional_ public methods; the facade dispatches to the richer method via `_fetch_from_adapter()`.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Direct API calls in the facade | Facade becomes a god class; untestable; hard to add sources |
| Shared HTTP helper base class | Forces HTTP as the mechanism; incompatible with future WebSocket/gRPC sources |

---

## ADR-003 — Two-layer deduplication (in-memory + DB) {#adr-003}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

The same job listing can appear from multiple sources simultaneously (e.g., an Adzuna job that also appears in an RSS feed), and the same ingestion cycle may be re-triggered (on startup or manually). Without deduplication, the DB would accumulate duplicate rows degrading data quality and search relevance.

### Decision

Deduplication is applied at **two independent layers**:

1. **In-memory (facade layer):** A `seen_urls` `set` tracks URLs as items are merged across adapters. The first source to surface a URL wins.
2. **Database layer:** `RssItemRepository.upsert_items()` uses PostgreSQL's `INSERT ... ON CONFLICT (guid) DO UPDATE` so re-running the same cycle is safe.

```python
# Layer 1 — in-memory, facade
def _dedup_extend(merged, seen_urls, items):
    for item in items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            merged.append(item)

# Layer 2 — DB, repository
stmt = pg_insert(RssItem).values(rows)
stmt = stmt.on_conflict_do_update(index_elements=["guid"], set_={...})
```

### Rationale

- **Defense in depth:** In-memory dedup reduces DB write load; DB-level dedup is the safety net for restarts, races, and future multi-process deployments.
- **Data integrity:** `created_at` is never overwritten (only `updated_at` is touched on conflict), preserving the first-seen timestamp for freshness scoring.
- **Efficiency:** Deduped batches sent to Postgres are smaller, reducing index contention.

### Consequences

- Two deduplication keys are in use: `url` (in-memory) and `guid` (DB). They should correlate; mismatches may still cause DB duplicates if guids diverge for the same URL.
- Additional within-batch deduplication inside `upsert_items()` guards against PostgreSQL's `CardinalityViolation` on conflicting rows in a single INSERT.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| DB-only dedup | Unnecessary round-trips for items already known to be duplicate in this cycle |
| Application-level SELECT before INSERT | `N+1` query pattern; not atomic under concurrent workers |

---

## ADR-004 — Async offloading via `run_in_executor` {#adr-004}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

`AggregatorFacade.fetch_all_opportunities()` performs multiple synchronous HTTP calls using `httpx` (blocking I/O). The ingestion worker runs inside the FastAPI async event loop. Calling blocking code directly in `async def` stalls the event loop and degrades API response latency for all concurrent requests.

### Decision

The worker runs the synchronous facade inside a thread-pool executor using `asyncio.get_running_loop().run_in_executor()`, keeping the event loop free.

```python
loop = asyncio.get_running_loop()
items = await loop.run_in_executor(None, facade.fetch_all_opportunities)
```

### Rationale

- **Non-blocking event loop:** FastAPI can continue serving user requests while ingestion I/O is in progress in a background thread.
- **Simplicity:** `run_in_executor` requires no changes to the synchronous adapter code. A full async rewrite of all adapters would be significant scope increase.
- **Standard pattern:** This is the idiomatic Python pattern for bridging sync/async boundaries.

### Consequences

- The thread pool uses Python's default `ThreadPoolExecutor`, which is CPU-count × 5 threads. Long-running adapter calls may exhaust this pool under high load.
- If the ingestion cycle duration exceeds the interval, cycles can overlap. This is acceptable at 30-minute intervals but should be guarded with a lock if the interval shrinks significantly.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Rewrite all adapters as `async def` with `httpx.AsyncClient` | Large refactor; all adapters would need rewriting; deferred for future sprint |
| Celery worker | Adds Redis/RabbitMQ infrastructure dependency for a single periodic task |
| Separate process (`multiprocessing`) | Over-engineering; adds IPC complexity |

---

## ADR-005 — Idempotent upsert with `ON CONFLICT DO UPDATE` {#adr-005}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

The ingestion cycle runs every 30 minutes. Service restarts trigger an immediate ingestion. Admin endpoints can trigger manual ingestion. Items ingested in a previous cycle will be seen again in subsequent cycles. The system must tolerate re-ingestion without creating duplicate rows or losing original metadata.

### Decision

Use PostgreSQL's `INSERT ... ON CONFLICT (guid) DO UPDATE` (upsert). On conflict, only volatile fields (title, summary, tags, published_at, updated_at) are updated; stable fields (guid, url, created_at) are preserved.

```sql
INSERT INTO rss_items (guid, title, url, ...)
VALUES (...)
ON CONFLICT (guid) DO UPDATE
  SET title = EXCLUDED.title,
      summary = EXCLUDED.summary,
      updated_at = NOW();
-- created_at is NOT in the SET clause → preserved forever
```

### Rationale

- **Idempotency:** Any number of re-runs for the same data produces exactly one row. This makes the worker safe to restart without cleanup.
- **Data freshness:** Titles and summaries can change on the source; the upsert refreshes them automatically.
- **Audit trail:** `created_at` always reflects the moment an opportunity was first discovered, valuable for freshness scoring features.

### Consequences

- Requires a unique constraint on `guid` in the `rss_items` table (already in place via `Base.metadata`).
- `rowcount` from PostgreSQL upserts includes both inserts and updates, so the returned `upserted` number cannot distinguish new from refreshed rows.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| SELECT then INSERT/UPDATE | Non-atomic; race conditions under concurrent ingestion |
| DELETE + re-INSERT | Destroys created_at; cascade deletes if FKs are added later |
| Skip already-seen guids | Stale titles/summaries never get refreshed |

---

## ADR-006 — Repository pattern for data access {#adr-006}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

Multiple components interact with the `rss_items` table: the ingestion worker (writes), the feeds API router (reads), and future analytics features (aggregates). Without an abstraction, every component would contain raw SQLAlchemy queries — duplicating filtering logic and making the DB schema hard to evolve.

### Decision

All DB access for `rss_items` is encapsulated in `RssItemRepository`. The repository owns query construction, filtering, pagination, upsert, and cleanup.

```python
repo = RssItemRepository(db)
repo.upsert_items(items)         # write path
repo.get_items(category="job")   # read path
repo.purge_old_items(days=30)    # maintenance
```

### Rationale

- **Single source of truth for queries:** Schema changes (e.g., adding a column) require edits only in the repository, not across every caller.
- **Testability:** The worker and router can be tested against a mock/stub repository without a real DB.
- **Consistency:** Filtering logic (e.g., ordering by `published_at DESC NULLS LAST`) is defined once and shared.

### Consequences

- The repository is tied to SQLAlchemy. Switching ORMs would require rewriting the repository but nothing else.
- Session lifecycle (open/close) is the caller's responsibility; the repository accepts an injected `Session`.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| Active Record (model owns queries) | Violates SRP; SQLAlchemy models become large |
| Inline SQL in routes | Duplicates query logic; untestable; schema brittleness |

---

## ADR-007 — Background loop via FastAPI lifespan + asyncio task {#adr-007}

**Status:** Accepted
**Deciders:** Engineering team
**Date:** 2026-04-18

### Context

Ingestion must run continuously in the background while the FastAPI server is live. It must start on application startup and shut down cleanly when the process exits (e.g., on SIGTERM during container restart).

### Decision

Register the `ingestion_loop()` coroutine as an `asyncio.create_task()` inside FastAPI's `@asynccontextmanager lifespan`. The task is cancelled in the `finally` block on shutdown.

```python
@asynccontextmanager
async def lifespan(_: FastAPI):
    ingestion_task = asyncio.create_task(ingestion_loop(), name="ingestion-worker")
    try:
        yield
    finally:
        ingestion_task.cancel()
        try:
            await ingestion_task
        except asyncio.CancelledError:
            pass
```

### Rationale

- **Process co-location:** No separate process/service is required; the worker shares the app's environment variables, DB connection pool, and logging setup.
- **Clean shutdown:** Cancellation is cooperative — the `asyncio.sleep` in the loop yields control, ensuring the cycle does not terminate mid-write.
- **Observability:** The task name (`"ingestion-worker"`) appears in asyncio debugging output and structured logs.

### Consequences

- The worker and web server share the same process. A crash in the worker surfaces as a failed asyncio task, not a process exit — the server continues serving but ingestion stops silently unless alerting is in place.
- Horizontal scaling (multiple pods) without a distributed lock would cause concurrent ingestion from all pods — acceptable now but should be addressed (e.g., with `pg_advisory_lock`) before multi-replica deployment.

### Alternatives Considered

| Alternative | Reason Rejected |
|-------------|-----------------|
| APScheduler | Additional dependency with its own state management |
| Celery Beat | Requires a broker (Redis/RabbitMQ); over-engineered for one periodic task |
| Kubernetes CronJob | Requires separate Docker image build; no shared DB pool or env |
| Threading (`threading.Timer`) | Does not integrate cleanly with asyncio event loop |

---

## Summary Matrix

| ADR | Pattern / Tactic | Primary NFR |
|-----|-----------------|-------------|
| 001 | Facade | Maintainability, Extensibility |
| 002 | Adapter | Interoperability, Substitutability |
| 003 | Two-layer deduplication | Data Consistency, Integrity |
| 004 | Async offloading | Performance, Responsiveness |
| 005 | Idempotent upsert | Fault Recovery, Reliability |
| 006 | Repository | Testability, Separation of Concerns |
| 007 | FastAPI lifespan task | Availability, Operational Simplicity |
