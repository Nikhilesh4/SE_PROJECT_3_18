# Task 4: Architecture Analysis & Quantitative Evaluation

**Project:** UniCompass — AI-Powered Opportunity Discovery Platform  
**Focus:** Evaluating the architectural trade-offs between the implemented **Hybrid Event-Driven Cache-Aside Architecture** and a traditional **Synchronous Monolithic Architecture**.

---

## 4.1 Architectures Compared

### A. The Implemented Architecture (Hybrid Event-Driven Cache-Aside)
The current UniCompass API decouples *data ingestion* from *data delivery*.
- **Delivery (Read Path):** API requests (e.g., `GET /api/feeds/rss`) operate over a Layered architecture but immediately intercept the request using a `@cached` Cache-Aside pattern. If data is in Redis, it skips the database entirely.
- **Ingestion (Write Path):** Background `asyncio` workers (`rss_refresh_loop`, `ingestion_loop`) run completely out-of-band. They fetch data, normalize it, and store it in PostgreSQL, then emit a cache-invalidation event.

### B. The Alternative (Synchronous Monolithic Architecture)
A standard N-Tier approach where every request is handled in real-time.
- **Unified Path:** A user request to the Discovery Feed triggers the backend to synchronously call the `AggregatorFacade`. The facade makes HTTP requests to 50+ RSS feeds and external APIs, merges the responses, and returns them to the user in a single blocking HTTP lifecycle. No background workers, no Redis cache.

---

## 4.2 Quantitative Analysis (Empirical Results)

The following metrics were captured using the `benchmark_arch.py` script running on the UniCompass prototype.

### 1. Response Time (Latency) - NFR-1
*Goal: Provide a sub-second interactive experience for opportunity discovery.*

| Scenario | Measured Latency (ms) | User Experience |
| :--- | :--- | :--- |
| **Current (Redis Cache Hit)** | **1.77 ms** | **Instantaneous** |
| **Current (PostgreSQL Cache Miss)** | **313.98 ms** | **Fast** |
| **Alternative (Sync Monolith)** | **153,828.43 ms** | **Broken (Timeout)** |

**Analysis:** The implemented architecture provides an **86,000x improvement** in response time. The alternative architecture exceeds the standard 30-second HTTP timeout limit, meaning users would receive a "504 Gateway Timeout" error instead of data.

---

### 2. System Throughput (Requests Per Second) - NFR-2
*Goal: Support concurrent users without server degradation.*

Throughput is calculated based on the maximum number of requests a single worker can process per second (`1000ms / Latency`).

| Pattern | Calculated Throughput (RPS) | Concurrent Capacity |
| :--- | :--- | :--- |
| **Current (Cache Hit)** | **~565 RPS** | High-Traffic Ready |
| **Current (DB Fallback)** | **~3.2 RPS** | Moderate Traffic |
| **Alternative (Sync)** | **0.006 RPS** | Fails at 1 user |

**Analysis:** The current architecture yields **80,000x higher throughput**. In the alternative pattern, the server's worker threads are "locked" waiting for external websites, causing a queue backup that would crash the server even with just 2 concurrent users.

---

### 3. Rate-Limit Scalability & Cost - NFR-3
*Goal: Minimize operational costs and avoid API blacklisting.*

- **Current Architecture (O(1) Load):** The background worker runs every 30 minutes. External API load is fixed at **48 calls/day**, regardless of the number of users.
- **Alternative Architecture (O(N) Load):** Every user refresh triggers calls to external APIs. With 1,000 users, the system would hit **2,000+ calls/day**, quickly exceeding free-tier limits and resulting in the application being blacklisted by providers like Adzuna or Jooble.

---

## 4.3 Trade-off Analysis

While the Performance gains are massive, architectural decisions always involve trade-offs.

### Trade-off 1: Performance vs. Data Freshness (Consistency)
- **Current (Eventual Consistency):** Users see data that might be up to 30 minutes old (the background refresh interval). However, they get this data instantly.
- **Alternative (Strong Consistency):** Users see data that is "live" at that exact second.
- **Decision:** For job discovery, a 30-minute delay is acceptable. We traded "absolute real-time accuracy" for "extreme speed and availability."

### Trade-off 2: Speed vs. Architectural Complexity
- **Current (High Complexity):** Requires managing a Redis instance, background task loops, and handling "stale" cache states. Debugging is harder because errors can happen in the background worker.
- **Alternative (Low Complexity):** Simple request-response loop. Easier to debug but unusable at scale.
- **Decision:** To build a platform that handles 50+ sources, the complexity of an **Event-Driven Cache-Aside** pattern is a necessary investment.

---

## 4.4 Conclusion
The prototype implementation successfully validates the proposed architecture. By shifting the "costly" network operations to the background and serving users from a high-speed cache, we achieved a response time of **1.77ms**, ensuring a premium, responsive experience that would be technically impossible under a traditional synchronous model.
