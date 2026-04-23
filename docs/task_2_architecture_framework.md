# Task 2: Architecture Framework

**Project:** UniCompass — AI-Powered Opportunity Discovery Platform for Students  
**Standard Applied:** IEEE 42010:2011 (Systems and Software Engineering — Architecture Description)  
**ADR Template:** Nygard ADR Format  

---

## Part 1: Stakeholder Identification (IEEE 42010)

> IEEE 42010:2011 defines an architecture description as a work product that documents an architecture in terms of **stakeholders**, their **concerns**, the **viewpoints** that frame those concerns, and the **views** that conform to those viewpoints.

---

### 1.1 Identified Stakeholders

Based on the UniCompass project requirements document, the following stakeholders have been identified:

| ID  | Stakeholder                     | Role / Description |
|-----|---------------------------------|--------------------|
| SH1 | **Undergraduate Students**      | Primary end-users who browse the discovery feed, filter opportunities, bookmark items, and upload resumes for AI-based profile extraction. |
| SH2 | **Postgraduate / Research Aspirants** | End-users who leverage the Semantic Scholar integration to discover research openings, published papers, and lab opportunities. |
| SH3 | **System Architects / Developers (Team 18)** | Design and build the system. Responsible for ensuring that architectural decisions align with quality attributes like scalability, maintainability, and performance. |
| SH4 | **Academic Evaluators / Teaching Assistants** | Assess project deliverables for compliance with software engineering standards, design pattern usage, and architectural quality. |
| SH5 | **External API Providers**      | Third-party services (Adzuna, Jooble, Semantic Scholar, Internshala RSS, HackerEarth RSS, DevPost RSS) whose APIs and feeds provide raw opportunity data to the system. |
| SH6 | **Database Administrator (Logical Role)** | Responsible for PostgreSQL schema design, pgvector extension management, and Redis configuration. May overlap with SH3 in a small team. |
| SH7 | **AI/ML Service Provider (Google DeepMind / Gemini)** | The Gemini API is used for resume parsing and structured data extraction; its availability, token limits, and API changes directly affect the system. |

---

### 1.2 Stakeholder Concerns

Each stakeholder has distinct concerns about the system that must be addressed by the architecture:

| Stakeholder | Key Concerns |
|-------------|-------------|
| **SH1 – Undergraduate Students** | Discovery feed loads quickly (< 200 ms for cached responses); opportunities are accurate, relevant, and up-to-date; resume parsing correctly identifies their skills; bookmarks are reliably persisted; the interface is intuitive and works on all devices. |
| **SH2 – Research Aspirants** | Research opportunities from Semantic Scholar are surfaced alongside jobs and internships; semantic ranking prioritizes relevance to academic interests; profile embeddings reflect postgraduate intentions. |
| **SH3 – Architects / Developers** | Clean separation of concerns across subsystems (Ingestion, Matching, API, Frontend); system is extensible to support new opportunity sources; background workers do not block the main API thread; codebase is maintainable and follows SOLID principles. |
| **SH4 – Academic Evaluators** | IEEE 42010–compliant architecture documentation; demonstrable use of recognized design patterns (Facade, Adapter, Strategy, Observer/Pub-Sub); adherence to the project requirements specification; clear ADRs justifying major decisions. |
| **SH5 – External API Providers** | Rate limits are respected; API keys are securely stored; failures in one provider do not cascade to others; source attribution is maintained in opportunity records. |
| **SH6 – Database Administrator** | Schema is normalized with appropriate indexing; pgvector extension is correctly installed; Redis TTLs and invalidation strategies prevent stale data; data deduplication prevents record proliferation. |
| **SH7 – AI/ML Service Provider (Gemini)** | API calls are well-formed and within quota; prompts are deterministic and produce structured JSON output; fallback behavior exists for API outages or malformed responses. |

---

### 1.3 Architecture Viewpoints

Following IEEE 42010, the following **viewpoints** are defined. Each viewpoint frames a set of stakeholder concerns and specifies the conventions for the corresponding view.

| Viewpoint ID | Viewpoint Name          | Addressed Concerns | Primary Stakeholders |
|--------------|-------------------------|--------------------|----------------------|
| VP-1 | **Functional / Logical Viewpoint** | What the system does; its key components and responsibilities. | SH1, SH2, SH3, SH4 |
| VP-2 | **Information / Data Viewpoint** | How data is structured, stored, and flows through the system. |  SH3, SH6 |
| VP-3 | **Deployment / Infrastructure Viewpoint** | How the system is deployed; the runtime environment and infrastructure. | SH3, SH6, SH5 |
| VP-4 | **Behavioral / Process Viewpoint** | How the system behaves over time; key workflows and interactions. | SH1, SH2, SH3 |
| VP-5 | **Performance & Caching Viewpoint** | How latency, throughput, and scalability requirements are met. | SH1, SH3, SH4, SH6 |

---

### 1.4 Architecture Views

Each view corresponds to one viewpoint and provides a concrete description of the architecture from that perspective.

---

#### View 1 — Functional / Logical View (VP-1)

This view describes the major logical subsystems of UniCompass and their responsibilities:

```
┌──────────────────────────────────────────────────────────────────────┐
│                        UniCompass System                             │
│                                                                      │
│  ┌───────────────┐    RESTful /    ┌──────────────────────────────┐  │
│  │  Frontend UI  │◄── WebSocket ──►│         Backend API          │  │
│  │  (Next.js /   │                 │  (FastAPI — Routers, Auth,   │  │
│  │   React)      │                 │   Feed, Profile Endpoints)   │  │
│  └───────────────┘                 └──────────────┬───────────────┘  │
│                                                   │                  │
│         ┌─────────────────────────────────────────┼─────────────┐    │
│         │                                         │             │    │
│  ┌──────▼──────┐   ┌────────────────┐   ┌────────▼──────────┐  │    │
│  │  Ingestion  │   │   Matching     │   │  AI/ML Service    │  │    │
│  │  Engine     │   │   Engine       │   │  (Gemini API /    │  │    │
│  │ (RSS/API    │   │ (pgvector +    │   │   PyMuPDF Resume  │  │    │
│  │  Adapters + │   │  Sentence-     │   │   Parsing)        │  │    │
│  │  Facade)    │   │  Transformers) │   └───────────────────┘  │    │
│  └──────┬──────┘   └───────┬────────┘                          │    │
│         │                  │                                    │    │
│  ┌──────▼──────────────────▼────────────────────────────────┐  │    │
│  │                    Persistence Layer                      │  │    │
│  │           PostgreSQL (+ pgvector) │ Redis Cache           │  │    │
│  └───────────────────────────────────────────────────────────┘  │    │
│                                                                  │    │
└──────────────────────────────────────────────────────────────────────┘
```

**Subsystem Responsibilities:**

| Subsystem | Responsibility |
|-----------|---------------|
| **Frontend UI** | Renders the discovery feed, manages authentication UI (login/register), provides resume upload UX, displays real-time notification bell via WebSocket. |
| **Backend API** | Orchestrates all business logic; exposes `/auth`, `/api/feed`, and `/profile` RESTful endpoints; manages JWT middleware; acts as WebSocket server for notifications. |
| **Ingestion Engine** | Polls external sources (RSS feeds via Feedparser, Adzuna API, Jooble API) on a periodic schedule; uses the Facade + Adapter pattern to normalize disparate data formats into a common `NormalizedRssItem` schema; deduplicates by source URL; upserts to PostgreSQL. |
| **Matching Engine** | Encodes opportunity text and user profiles as vector embeddings (Sentence-Transformers); stores embeddings in PostgreSQL via pgvector; performs cosine similarity search for relevance-based feed sorting. |
| **AI/ML Service** | Receives uploaded PDF resumes; extracts raw text via PyMuPDF; sends text to Gemini API with a structured prompt; parses returned JSON for skills, education, and experience. |
| **Persistence Layer** | PostgreSQL serves as the primary relational data store (users, opportunities, bookmarks, profiles, embeddings). Redis serves as a high-speed cache for feed responses, profile data, and a Pub/Sub broker for real-time notification events. |

---

#### View 2 — Information / Data View (VP-2)

This view describes the primary data entities and how data flows through the system:

**Core Data Entities:**

| Entity | Primary Store | Key Attributes |
|--------|--------------|----------------|
| `User` | PostgreSQL | id, name, email, hashed_password, skills[], interests[], profile_embedding (vector) |
| `Opportunity (rss_items)` | PostgreSQL | id, title, url (unique key for dedup), source, category, published_at, deadline, embedding (vector) |
| `Bookmark` | PostgreSQL | user_id (FK), opportunity_id (FK), created_at |
| `UserProfile` | PostgreSQL | user_id (FK), extracted_skills, education, experience (jsonb) |
| `Feed Cache` | Redis | Key: `feed:{category}:{sort}:{page}`, TTL: 5–10 min |
| `Profile Cache` | Redis | Key: `profile:{user_id}`, TTL: 1 hour |
| `Opportunity Cache` | Redis | Key: `opportunity:{id}`, TTL: 30 min |
| `Notification Event` | Redis Pub/Sub | Channel: `notifications:{user_id}`, payload: opportunity match |

**Data Flow — Ingestion Pipeline:**
```
External Sources (RSS/Adzuna/Jooble)
        │
        ▼
[Adapter Layer] — Parse & normalize to NormalizedRssItem
        │
        ▼
[AggregatorFacade] — Merge + deduplicate by source URL
        │
        ▼
[Background Worker] — Upsert to PostgreSQL rss_items table
        │
        ▼
[Matching Engine] — Compute embeddings, store via pgvector
        │
        ▼
[Redis Cache Invalidation] — Clear stale feed:{*} keys
```

**Data Flow — Resume Upload:**
```
User uploads PDF (Frontend)
        │
        ▼
POST /profile/upload-resume (Backend API)
        │
        ▼
PyMuPDF — Extract raw text
        │
        ▼
Gemini API — Structured JSON (skills, education, experience)
        │
        ▼
PostgreSQL — Persist UserProfile
        │
        ▼
Redis — Invalidate profile:{user_id}
```

---

#### View 3 — Deployment / Infrastructure View (VP-3)

This view describes how UniCompass components are deployed across infrastructure:

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Docker Compose Network                         │
│                                                                     │
│  ┌──────────────────┐   ┌──────────────────┐   ┌────────────────┐  │
│  │   frontend       │   │   backend        │   │  postgres      │  │
│  │  (Next.js)       │   │  (FastAPI /      │   │  (PostgreSQL + │  │
│  │  Port: 3000      │◄──►  Uvicorn)        │◄──►  pgvector)     │  │
│  │                  │   │  Port: 8000      │   │  Port: 5432    │  │
│  └──────────────────┘   └────────┬─────────┘   └────────────────┘  │
│                                  │                                  │
│                         ┌────────▼─────────┐                       │
│                         │   redis          │                       │
│                         │  (Redis Server)  │                       │
│                         │  Port: 6379      │                       │
│                         └──────────────────┘                       │
│                                                                     │
│  Configuration: docker-compose.yml                                  │
│  Secrets: .env.local (API keys for Gemini, Adzuna, Jooble)         │
└─────────────────────────────────────────────────────────────────────┘
```

- The **Frontend** and **Backend** communicate over HTTP/REST and WebSockets.
- The **Backend** communicates with PostgreSQL via SQLAlchemy and with Redis via an async Redis client.
- **Background workers** (`rss_refresh_loop`, `ingestion_loop`) run as asyncio tasks within the FastAPI process lifecycle (managed via the `lifespan` context manager in `main.py`).
- External API keys are stored securely in environment variables, never committed to source control.

---

#### View 4 — Behavioral / Process View (VP-4)

This view describes the key runtime workflows:

**Workflow 1: User Registration & Login**
```
User → POST /auth/register (name, email, password, skills, interests)
      → Backend hashes password (bcrypt)
      → PostgreSQL stores User record
      → Return 201 Created

User → POST /auth/login (email, password)
      → Backend verifies bcrypt hash
      → Issues JWT (HS256, 24h expiry)
      → Frontend stores JWT in browser storage
      → All subsequent requests: Authorization: Bearer <JWT>
```

**Workflow 2: Discovery Feed Request**
```
User → GET /api/feed?category=internship&sort=latest&page=1
      → JWT Middleware validates token
      → Redis: Check key feed:internship:latest:1
          ├─ HIT  →  Return cached JSON (< 200 ms)
          └─ MISS →  Query PostgreSQL rss_items
                  →  Sort / Filter (Strategy pattern)
                  →  Store in Redis (TTL: 5 min)
                  →  Return response
```

**Workflow 3: Periodic Ingestion (Background Worker)**
```
[Ingestion Worker — asyncio loop, every N minutes]
      → AggregatorFacade.fetch_all_opportunities()
          ├─ RSSAdapter (Feedparser → Internshala, HackerEarth, DevPost)
          ├─ AdzunaAdapter (Adzuna REST API)
          └─ JoobleAdapter (Jooble REST API)
      → Deduplicate by source URL
      → Upsert to PostgreSQL (INSERT ON CONFLICT DO NOTHING)
      → [Matching Engine] Generate + store embeddings
      → Invalidate Redis feed:{*} keys
      → [Notification Service] Pub/Sub: notify matched users
```

**Workflow 4: Real-Time Notification**
```
[Ingestion Worker detects high-relevance match for user U]
      → Redis PUBLISH notifications:U <opportunity_payload>
      → WebSocket server SUBSCRIBE
      → WebSocket server PUSH to connected client U
      → Frontend: notification bell badge increments
```

---

#### View 5 — Performance & Caching View (VP-5)

This view directly addresses the `NFR-1: Performance (< 200 ms)` and `NFR-2: Scalability` concerns:

**Multi-Layer Redis Caching Strategy:**

| Cache Layer | Redis Key Pattern | TTL | Invalidation Trigger |
|------------|-------------------|-----|----------------------|
| Discovery Feed | `feed:{category}:{sort}:{page}` | 5–10 min | Ingestion worker completes |
| Opportunity Detail | `opportunity:{id}` | 30 min | Never (immutable after ingestion) |
| User Profile | `profile:{user_id}` | 1 hour | Resume re-upload |
| External API Raw Response | `source:{source_name}:latest` | 30 min | Time-based expiry |

**Scalability Tactics:**
- Background ingestion runs as **non-blocking asyncio tasks**, preventing main API thread starvation.
- Deduplication at the facade layer prevents exponential table growth.
- pgvector's HNSW index enables sub-linear similarity search across large embedding sets.
- Redis Pub/Sub decouples notification fan-out from the ingestion write path.

---

## Part 2: Architecture Decision Records (ADRs)

> All ADRs follow the **Nygard ADR Template** as described at: https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions

---

### ADR-001: Adopt FastAPI as the Backend API Framework

**Status:** Accepted

#### Context

UniCompass requires a backend framework capable of:
1. Serving RESTful endpoints with minimal boilerplate for a rapid-prototype timeline.
2. Supporting **asynchronous** programming to run background ingestion workers alongside API request handling.
3. Providing first-class **WebSocket** support for real-time notification delivery.
4. Offering automatic **OpenAPI / Swagger UI** generation for development and evaluator review.

The alternatives evaluated were:

| Framework | Async Support | Auto-docs | Learning Curve | WebSocket |
|-----------|:---:|:---:|:---:|:---:|
| Django REST Framework | Partial (via channels) | No (manual) | High | Plugin-dependent |
| Flask | No (native sync) | No | Low | Plugin-dependent |
| **FastAPI** | **Native (asyncio)** | **Yes (automatic)** | **Low-Medium** | **Built-in** |
| Express.js (Node) | Yes | No | Low | Yes |

The team's primary language competency is Python. A Python-native framework was strongly preferred to minimize overhead from language-switching.

#### Decision

We will use **FastAPI** as the backend web framework, with **Uvicorn** as the ASGI server.

#### Consequences

**Positive:**
- Native `async/await` support allows `rss_refresh_loop` and `ingestion_loop` to run as concurrent `asyncio.Task` objects within the same process, managed cleanly via FastAPI's `lifespan` context manager.
- Pydantic-based schema validation (e.g., `NormalizedRssItem`) provides automatic request/response validation and documentation.
- Built-in WebSocket support (`/ws/notifications`) enables real-time notifications without additional infrastructure.
- Auto-generated Swagger UI (`/docs`) aids academic evaluation and testing.

**Negative / Trade-offs:**
- Being a single-process ASGI application, CPU-bound tasks (embedding generation) can block the event loop. This is mitigated by offloading heavy embedding computation to background worker tasks.
- FastAPI's ecosystem is smaller than Django's; some enterprise features (admin panels, ORM migrations) require third-party libraries.

---

### ADR-002: Use the Facade + Adapter Pattern for Multi-Source Data Ingestion
 
**Status:** Accepted

#### Context

UniCompass must aggregate opportunity data from fundamentally heterogeneous sources:
- **RSS Feeds** (Internshala, HackerEarth, DevPost) — XML parsed via `feedparser`
- **Adzuna API** — RESTful JSON API with proprietary query parameters
- **Jooble API** — RESTful JSON API with a different schema
- **Semantic Scholar API** — RESTful JSON API for academic research opportunities

Each source returns data in a different format. The system requires a **single, unified data model** (`NormalizedRssItem` / `OpportunityCard`) for storage and presentation. Without a pattern, each consuming component (background worker, ingestion endpoint, tests) would contain source-specific parsing logic — a direct violation of the Open/Closed Principle.

#### Decision

We will implement a **two-tier structural pattern**:

1. **Adapter Pattern** — Each source gets its own adapter class that implements the `OpportunityAdapter` interface, translating source-specific formats into `NormalizedRssItem`. Adapters: `RSSAdapter`, `AdzunaAdapter`, `JoobleAdapter`, `AIProfileAdapter`.

2. **Facade Pattern** — `AggregatorFacade` provides a single `fetch_all_opportunities()` method. It orchestrates all adapters, merges results, and deduplicates by source URL. Downstream consumers (the ingestion worker, API endpoints) never interact with individual adapters.

```python
# Facade usage — downstream code is completely source-agnostic
facade = AggregatorFacade()
all_items = facade.fetch_all_opportunities()  # RSS + Adzuna + Jooble, deduplicated
```

#### Consequences

**Positive:**
- **Open/Closed Principle**: Adding a new source (e.g., Semantic Scholar) requires only creating a new class implementing `OpportunityAdapter` and registering it with `AggregatorFacade` — zero changes to existing code.
- **Fault Isolation**: Each adapter's failure is caught independently; a Jooble API outage does not prevent RSS items from being ingested.
- **Testability**: Individual adapters can be unit-tested in isolation; the facade can be tested with mock adapters.
- **Deduplication**: The facade performs URL-based deduplication in a single pass, preventing PostgreSQL record bloat.

**Negative / Trade-offs:**
- Introduces additional abstraction layers and file count. For a small project, this adds complexity that a simple function-based approach would not.
- The `_fetch_from_adapter` dispatch method in `AggregatorFacade` currently uses `isinstance` checks, which is a code smell. This can be resolved by standardizing the adapter interface method name in a future refactor.

---

### ADR-003: Use PostgreSQL with pgvector Extension for Unified Storage and Semantic Search

**Status:** Accepted

#### Context

UniCompass requires two distinct data management capabilities:
1. **Relational storage** for structured entities: users, opportunities, bookmarks, authentication.
2. **Vector similarity search** for semantic relevance ranking: given a user profile embedding vector, find the top-K most similar opportunity vectors.

The alternatives for the vector search component were:

| Option | Description | Trade-off |
|--------|-------------|-----------|
| Separate vector DB (Pinecone, Weaviate) | Dedicated vector database alongside PostgreSQL | Added infrastructure, data synchronization overhead, additional cost |
| Pure keyword search (PostgreSQL FTS) | PostgreSQL Full-Text Search | No semantic understanding; keyword matching only |
| **pgvector** | PostgreSQL extension for vector storage & similarity | Single database, no sync needed, cosine similarity via SQL |
| ChromaDB (embedded) | Lightweight local vector DB | Not production-grade; difficult to scale; no relational joins |

A key constraint was the team's desire to minimize infrastructure complexity within a Docker Compose setup for a prototype. Running a separate vector database service would have added another container, synchronization logic, and failure modes.

#### Decision

We will use a **single PostgreSQL instance with the `pgvector` extension** to serve both relational storage and vector similarity search.

- Opportunity embeddings are stored as `vector(384)` columns in the `rss_items` table (384-dimensional output from `all-MiniLM-L6-v2` Sentence-Transformer model).
- User profile embeddings are stored as `vector(384)` in the `users` table.
- Cosine similarity queries are expressed as standard SQL:
  ```sql
  SELECT * FROM rss_items
  ORDER BY embedding <=> :user_embedding
  LIMIT 20;
  ```
- Application startup executes `CREATE EXTENSION IF NOT EXISTS vector` to ensure pgvector is available.

#### Consequences

**Positive:**
- **Single source of truth**: No data synchronization between a relational DB and a vector DB.
- **Transactional consistency**: Vector updates and relational updates are atomic within the same PostgreSQL transaction.
- **Simplified Docker setup**: One `postgres` container serves both functions; no additional service.
- **SQL expressiveness**: Vector search can be combined with WHERE filters (e.g., `category = 'internship'`) in a single query — impossible when using a separate vector database.

**Negative / Trade-offs:**
- pgvector's HNSW/IVFFlat index performance is lower than dedicated vector databases (Pinecone, Milvus) at very large scales (> 1M vectors). For a student-facing prototype, this is acceptable.
- Requires the `pgvector` extension to be pre-installed in the PostgreSQL Docker image, adding a build dependency.
- Embedding generation (CPU-bound, Sentence-Transformers) must be managed carefully to avoid blocking the async event loop.

---

### ADR-004: Implement Redis for Multi-Purpose Caching and Real-Time Pub/Sub

**Status:** Accepted

#### Context

Two separate architectural challenges can be addressed by Redis:

**Challenge A — Performance:** The discovery feed (`GET /api/feed`) is the most frequently accessed endpoint. Without caching, every request triggers a full PostgreSQL query, including potential vector similarity computation. The NFR specifies < 200 ms load time. PostgreSQL queries with vector search can easily exceed this on commodity hardware.

**Challenge B — Real-Time Notifications:** The system must push notifications to users when new relevant opportunities arrive. Options for implementation were:

| Option | Description | Trade-off |
|--------|-------------|-----------|
| HTTP Polling | Frontend polls `/notifications` every N seconds | High server load; latency = poll interval |
| Server-Sent Events (SSE) | One-way streaming from server to client | No broadcast mechanism; harder to fan-out |
| **Redis Pub/Sub + WebSocket** | Backend publishes events to Redis; WS server pushes to clients | Low latency; natural fan-out; decouples ingestion from notification |
| Full message queue (RabbitMQ, Kafka) | Enterprise message broker | Over-engineered for prototype; adds infrastructure |

#### Decision

We will deploy a single **Redis instance** to serve both roles:

1. **Cache Layer**: API responses are cached with structured key patterns and TTLs. A `@cache` decorator wraps endpoint handlers transparently. Cache invalidation is event-driven (ingestion completion) or time-based (TTL expiry).

2. **Pub/Sub Broker**: The ingestion worker publishes matched opportunity events to Redis channels (`notifications:{user_id}`). The FastAPI WebSocket handler subscribes to these channels and pushes messages to connected clients.

**Cache Key Design:**
```
feed:{category}:{sort}:{page}      → TTL 5–10 min
opportunity:{id}                   → TTL 30 min
profile:{user_id}                  → TTL 1 hour
source:{source_name}:latest        → TTL 30 min (ingestion-side)
```

#### Consequences

**Positive:**
- **Performance**: Cache hits serve the discovery feed in < 200 ms, directly satisfying NFR-1.
- **Scalability**: Cached responses reduce database load proportional to cache hit rate; allows the system to serve more concurrent users without scaling PostgreSQL.
- **Decoupling**: Redis Pub/Sub decouples the ingestion worker from notification delivery. The worker does not need to maintain WebSocket connections.
- **Dual-use efficiency**: A single Redis container serves both caching and messaging, keeping the Docker Compose topology minimal.
- **Graceful degradation**: If Redis is unavailable, the cache service falls back to direct database queries (cache miss path), so the system remains functional.

**Negative / Trade-offs:**
- Redis is an in-memory store; cache data is lost on Redis restart. This is acceptable since all caches are derived from the persistent PostgreSQL store.
- Cache invalidation for feed keys uses a pattern-based deletion (`feed:*`), which requires a Redis KEYS/SCAN operation. At scale, this could be slow; a more structured invalidation registry may be needed.
- Running Redis and PostgreSQL in Docker Compose adds memory pressure on development machines.

---

### ADR-005: Adopt JWT-Based Stateless Authentication
 
**Status:** Accepted

#### Context

UniCompass requires authentication to protect user-specific endpoints (profile, bookmarks, resume upload). The two primary approaches are:

| Approach | Description | Trade-off |
|----------|-------------|-----------|
| Session-Based Auth | Server stores session state; client sends session cookie | Requires shared session store (Redis) to work across multiple server instances; statefulness complicates horizontal scaling |
| **JWT (Stateless)** | Server issues signed token; client includes it in every request; server verifies signature without DB lookup | Stateless; scales horizontally; revocation requires a blacklist or short TTL |
| OAuth 2.0 + Social Login | Delegate auth to Google/GitHub | Good UX but complex integration; out of scope for prototype |

Given that UniCompass is a prototype and the team desired a clean, minimal authentication mechanism without requiring a session store (Redis is already used for caching, not authentication), stateless JWT was chosen.

#### Decision

We will use **JWT (JSON Web Tokens) with HS256 signing** for authentication:

- `POST /auth/register`: Creates user, hashes password with `bcrypt`, stores in PostgreSQL.
- `POST /auth/login`: Verifies bcrypt hash, returns signed JWT with `user_id` and `exp` claims (24-hour expiry).
- **JWT Middleware** validates the `Authorization: Bearer <token>` header on all protected routes by verifying the signature and expiry without a database round-trip.
- The frontend stores the JWT in `localStorage` and appends it to all API requests.

#### Consequences

**Positive:**
- **Stateless**: The backend does not need to maintain session state; any server instance can validate any JWT using the shared secret.
- **Simplicity**: Clean implementation with `python-jose` / `PyJWT`; no additional infrastructure (no session table, no session Redis key).
- **Performance**: Token validation is a cryptographic operation (microseconds) — no database lookup on every request.
- **Standard**: JWT is a widely understood standard (RFC 7519), making the implementation auditable and interoperable.

**Negative / Trade-offs:**
- JWTs cannot be individually revoked before expiry without a blacklist. For a prototype, the 24-hour TTL and "logout by deleting local storage" pattern is acceptable.
- The shared HS256 secret must be kept secure in the `.env.local` file. If compromised, all issued tokens are vulnerable.
- JWT payload is base64-encoded (not encrypted); sensitive data must not be stored in the payload. Only `user_id`, `email`, and `exp` are included.

---

## Summary

| Section | Coverage |
|---------|----------|
| **IEEE 42010 Stakeholders** | 7 stakeholders identified (SH1–SH7) |
| **Stakeholder Concerns** | Concerns mapped per stakeholder |
| **Viewpoints** | 5 viewpoints defined (VP-1 to VP-5) |
| **Views** | 5 views provided (Functional, Data, Deployment, Behavioral, Performance) |
| **ADR-001** | FastAPI as backend framework |
| **ADR-002** | Facade + Adapter pattern for ingestion |
| **ADR-003** | PostgreSQL + pgvector for unified storage |
| **ADR-004** | Redis for caching + Pub/Sub |
| **ADR-005** | JWT stateless authentication |
