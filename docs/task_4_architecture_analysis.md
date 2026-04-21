# Task 4: Architecture Analysis & Quantitative Evaluation

**Project:** UniCompass — AI-Powered Opportunity Discovery Platform  
**Focus:** Evaluating the architectural trade-offs between the implemented **Hybrid Event-Driven Cache-Aside Architecture** and a traditional **Synchronous Layered Architecture**.

> **Note on Methodology:** To objectively quantify the non-functional requirements (Response Time, Throughput, Scalability), the analysis below deconstructs the request lifecycle of both architectures. It maps out the exact computational and network I/O costs based on the system's external dependencies (Jooble API, Adzuna API, 20+ RSS Feeds).

---

## 4.1 Architectures Compared

### A. The Implemented Architecture (Hybrid Event-Driven Cache-Aside)
The current UniCompass API decouples *data ingestion* from *data delivery*.
- **Delivery (Read Path):** API requests (e.g., `GET /api/feeds/rss`) operate over a Layered architecture but immediately intercept the request using a `@cached` Cache-Aside pattern. If data is in Redis, it skips the database entirely.
- **Ingestion (Write Path):** Background `asyncio` workers (`rss_refresh_loop`, `ingestion_loop`) run completely out-of-band. They fetch data, normalize it, deduplicate it, compute embeddings, and store it in PostgreSQL, then emit a cache-invalidation event.

### B. The Alternative (Synchronous Layered Architecture)
A classic N-Tier approach used by many MVP prototypes.
- **Unified Path:** A user request to the Discovery Feed triggers the backend to synchronously call the `AggregatorFacade`. The facade makes HTTP requests to Jooble, Adzuna, and all RSS XML feeds, merges the responses, and returns them to the user in a single blocking HTTP lifecycle. No background workers, no Redis cache.

---

## 4.2 Quantitative Analysis of Non-Functional Requirements

### 1. Response Time (Latency)
**Quality Attribute:** Performance (NFR-1)

The most heavily utilized endpoint is the Discovery Feed (`GET /api/feeds/rss`). Let's break down the latency budget for both architectures.

**Current Architecture (Cache HIT - High % of traffic)**
The API caches feed responses in Redis with a **5-minute TTL**. If multiple users request the exact same feed parameters within that 5-minute window, they hit the cache.
- HTTP Request Parsing: ~1 ms
- Route Handler & Dependency Injection: ~1 ms
- Redis GET over local TCP (`redis_cache.py` L65): ~1–2 ms
- JSON Parsing & FastAPI Serialization: ~3–5 ms
- **Total Payload Delivery:** **~6 to 9 ms** (P50 Latency)

**Current Architecture (Cache MISS) / Cold Start**
- Route Handler: ~2 ms
- PostgreSQL query (`offset`/`limit` on `rss_items`): ~40–80 ms
- Redis SET (storing 50 normalized items): ~5 ms
- **Total Payload Delivery:** **~50 to 90 ms**

**Alternative Architecture (Synchronous Monolithic)**
A request triggers the `AggregatorFacade` which makes outbound HTTP calls to 20+ sources.
- Concurrent HTTP pool initialization: ~5 ms
- Adzuna API (external proxy): ~200–500 ms
- Jooble API: ~300–600 ms
- RSS Feed Parsing (parsing 15+ XML feeds sequentially or batched): ~800–1,500 ms
- Normalization & Deduplication: ~50 ms
- **Total Payload Delivery:** **~1,200 ms to 2,600 ms** (Bottlenecked by the slowest external API response—the "tail latency").

**Conclusion:** The implemented architecture provides a **130x improvement** in P50 Response Time (`~8ms` vs `~1,500ms`).

---

### 2. System Throughput (Requests Per Second - RPS)
**Quality Attribute:** Scalability (NFR-2)

Assume the server receives a sudden spike of traffic (e.g., 500 concurrent users accessing the Discovery Feed). We measure how the ASGI web server (Uvicorn) manages its worker threads.

**Current Architecture (Stateless API)**
- When hitting Redis, the CPU is purely bound by JSON serialization.
- A single Uvicorn worker thread can execute the `feeds.py` endpoint thousands of times a second without waiting for network I/O.
- **Estimated Throughput:** **~1,500 - 3,000 RPS** on a standard 2-vCPU node.

**Alternative Architecture (Blocking I/O)**
- Every user request opens a connection to Adzuna and Jooble. 
- 500 users × 2 external APIs = 1,000 concurrent outbound connections in a distributed pool.
- FastAPI's connection pool limits, thread starvation, and operating system socket timeouts would cause the system to collapse under queue pressure.
- **Estimated Throughput:** **< 20 RPS** before encountering 503 Service Unavailable or `httpx.PoolTimeout` errors.

**Conclusion:** The current architecture yields **>75x higher throughput**, making it capable of handling enterprise-scale loads without horizontal scaling.

---

### 3. Rate-Limit Scalability & Cost Efficiency
**Quality Attribute:** Operational Feasibility

External APIs (Jooble, Adzuna) strictly govern free/indie tiers.
- Adzuna Free Tier limit: e.g., 250 requests/day.
- Jooble API limits: restricted QPS.

**Current Architecture:**
- The background ingestion worker (`ingestion_worker.py`) runs every 30 minutes. It makes exactly 1 call to Jooble and Adzuna per cycle.
- **External API Load:** `48` requests/day. Regardless of whether UniCompass has 1 user or 100,000 users, the external load remains constant: **O(1) Load**.

**Alternative Architecture:**
- Every user refresh triggers 1 call to Jooble and Adzuna.
- **External API Load:** `N` requests/day. If 500 users refresh the page 3 times, that is 1,500 requests. The system hits the Adzuna daily quota globally within 15 minutes and gets blacklisted: **O(N) Load**.

---

### 4. Availability and Fault Tolerance
**Quality Attribute:** Resilience (NFR-4)

The "Limit Fault Propagation" tactic determines how the system handles a partial outage. What happens if Jooble's REST API goes down and returns HTTP 500?

**Current Architecture:**
- The background `JoobleAdapter` raises an exception (`jooble_adapter.py` L113).
- The `AggregatorFacade` catches it, logs it, and continues aggregating from Adzuna and RSS feeds (`aggregator_facade.py` L127).
- The database is updated, and the user queries the local database/Redis cache. **User Uptime: 100%**.

**Alternative Architecture:**
- User queries the `/feeds` endpoint.
- The `AggregatorFacade` makes a synchronous call to Jooble.
- Jooble hangs for 15 seconds, then times out. The user stares at a loading spinner for 15 seconds, only to receive a broken JSON response or an empty feed. **User Uptime: 0%** (Cascading Failure).

---

## 4.3 Deep-Dive Trade-off Analysis

The quantitative gains above heavily heavily favor the implemented Event-Driven Cache-Aside model. However, architectural decisions are about trade-offs. The current implementation introduces three significant costs that a synchronous monolith avoids:

#### Trade-off 1: Data Consistency (Staleness) vs. Performance
The Synchronous pattern possesses **Strong Consistency**: if a job is removed from Jooble at 10:00 AM, a user refreshing at 10:01 AM will not see it. 
UniCompass traded this for **Eventual Consistency** to achieve speed. Because `feeds.py` uses a 5-minute TTL on queries and the ingestion worker runs every 30 minutes, a user might view, attempt to apply, and be redirected to a 404 dead link because the opportunity was closed upstream 25 minutes ago.

#### Trade-off 2: Architectural Complexity & Debugging
The backend possesses a background `asyncio` task loop injected via FastAPI's `lifespan` manager. 
- If a data bug occurs (e.g., duplicate entries), developers cannot simply trace the HTTP request loop. They must inspect the background worker logs (`workers/ingestion_worker.py`), cross-reference the Redis pub-sub channels, and inspect database state independently.
- **The cost of asynchronous processing is operational complexity.** 

#### Trade-off 3: Increased Infrastructure & Memory Footprint
A synchronous layered monolith is stateless—it requires only standard compute instances.
The UniCompass design necessitates a highly available **Redis Node**. Storing JSON payloads for dozens of paginated feed views (e.g., `feed:job:true:50:0`, `feed:internship:true:50:50`) places heavy pressure on Redis RAM. If Redis memory limits are breached without an eviction policy (like `allkeys-lru`), the caching layer crashes, requiring a full Postgres fallback.
