# 🧭 UniCompass

> **AI-powered opportunity discovery platform** — Internships, Jobs, Hackathons, and Research opportunities aggregated, ranked by your skill profile, and served in milliseconds via Redis caching.

---

## 📑 Table of Contents

1. [Project Overview](#1-project-overview)
2. [Features](#2-features)
3. [Tech Stack](#3-tech-stack)
4. [Architecture Overview](#4-architecture-overview)
   - 4.1 [Layered Architecture](#41-layered-architecture)
   - 4.2 [Event-Driven Background Workers](#42-event-driven-background-workers)
   - 4.3 [Cache-Aside Pattern (Redis)](#43-cache-aside-pattern-redis)
   - 4.4 [Strategy Pattern (Feed Fetching)](#44-strategy-pattern-feed-fetching)
   - 4.5 [Facade Pattern (API Gateway)](#45-facade-pattern-api-gateway)
5. [Project Structure](#5-project-structure)
6. [Prerequisites](#6-prerequisites)
7. [Setup & Installation](#7-setup--installation)
   - 7.1 [Clone the Repository](#71-clone-the-repository)
   - 7.2 [Start Infrastructure (Docker)](#72-start-infrastructure-docker)
   - 7.3 [Backend Setup](#73-backend-setup)
   - 7.4 [Frontend Setup](#74-frontend-setup)
8. [Environment Variables](#8-environment-variables)
9. [Running the Application](#9-running-the-application)
10. [API Reference](#10-api-reference)
    - 10.1 [Authentication](#101-authentication)
    - 10.2 [Feeds](#102-feeds)
    - 10.3 [Profile](#103-profile)
11. [Design Patterns Reference](#11-design-patterns-reference)
12. [Code Documentation Guide](#12-code-documentation-guide)
13. [Testing](#13-testing)
14. [Contributing](#14-contributing)

---

## 1. Project Overview

**UniCompass** is a full-stack web application that helps university students discover curated opportunities — internships, jobs, hackathons, and research positions — all in one place.

The system continuously ingests RSS/Atom feeds in the background, normalises them into a unified schema, and stores them in PostgreSQL. When a user provides their skill profile (extracted from an uploaded resume), the feed is re-ranked using a relevance scoring algorithm that weights tag matches, title matches, and description mentions — ensuring the most personally relevant opportunities always surface first.

Redis is used as a read-through cache (Cache-Aside Pattern) with a 5-minute TTL, so repeated requests to the same endpoint are served in < 5 ms without touching the database.

---

## 2. Features

| Feature | Description |
|---|---|
| 🔐 **Authentication** | JWT-based login/register with bcrypt password hashing |
| 📄 **Resume Parsing** | Upload a PDF resume; Google Generative AI extracts skills automatically |
| 🔍 **Skill-Ranked Discovery** | Feed items are globally scored and ranked against your extracted skills |
| ⚡ **Redis Caching** | Cache-Aside with per-user skill-hash keys; cold-start < 200 ms, warm < 5 ms |
| 🔄 **Background Ingestion** | Two asyncio workers continuously refresh and invalidate RSS data |
| 📊 **Cache Observability** | Every API response includes a `from_cache` flag for transparency |
| 🗂️ **Category Filtering** | Filter by `internships`, `jobs`, `hackathons`, `research` |

---

## 3. Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Web Framework | [FastAPI](https://fastapi.tiangolo.com/) |
| Database | [PostgreSQL 16](https://www.postgresql.org/) + [pgvector](https://github.com/pgvector/pgvector) |
| Cache | [Redis 7](https://redis.io/) |
| ORM | [SQLAlchemy](https://www.sqlalchemy.org/) |
| Auth | JWT via `python-jose`, passwords via `passlib[bcrypt]` |
| AI / NLP | [Google Generative AI](https://ai.google.dev/) (Gemini) |
| RSS Parsing | [feedparser](https://feedparser.readthedocs.io/) |
| PDF Parsing | [PyMuPDF](https://pymupdf.readthedocs.io/) |

### Frontend
| Layer | Technology |
|---|---|
| Framework | [Next.js 14](https://nextjs.org/) (App Router) |
| Language | TypeScript |
| Styling | CSS Modules / Vanilla CSS |
| HTTP Client | Fetch API (Next.js API Routes as Facade/Gateway) |

### Infrastructure
| Service | Tool |
|---|---|
| Containerisation | Docker + Docker Compose |
| RSS Bridge | [RSS-Bridge](https://github.com/RSS-Bridge/rss-bridge) |

---

## 4. Architecture Overview

### 4.1 Layered Architecture

The system is structured in strict layers; each layer only communicates with the one directly below it.

```
┌──────────────────────────────────────────────┐
│  Presentation Layer   (Next.js pages/hooks)  │
├──────────────────────────────────────────────┤
│  API Gateway Layer    (Next.js API Routes)   │  ← Facade
├──────────────────────────────────────────────┤
│  Application Layer    (FastAPI Routers)       │
├──────────────────────────────────────────────┤
│  Service Layer        (Business Logic)        │
├──────────────────────────────────────────────┤
│  Repository Layer     (DB abstraction)        │
├──────────────────────────────────────────────┤
│  Infrastructure       (PostgreSQL + Redis)    │
└──────────────────────────────────────────────┘
```

**Rationale**: Layering enforces separation of concerns, makes each tier independently testable, and allows layers to be swapped (e.g., replacing Redis with Memcached) without touching business logic.

---

### 4.2 Event-Driven Background Workers

Two background `asyncio` tasks run continuously inside the FastAPI lifespan:

- **`rss_refresh_loop`** — Fetches all RSS sources every N minutes and upserts into the `rss_items` table.
- **`ingestion_loop`** — After each ingestion batch, invalidates all `feed:*` keys in Redis, ensuring users never see stale data after a refresh.

```
RSS Sources ──► rss_refresh_loop ──► PostgreSQL
                                         │
                                    ingestion_loop
                                         │
                                    Redis Invalidation ──► Clean Cache
```

---

### 4.3 Cache-Aside Pattern (Redis)

Every feed request checks Redis before touching the database:

```
Request ──► Redis HIT? ──YES──► Return (from_cache=True)
                │
               NO
                │
            DB Query / Scoring
                │
            Write to Redis (TTL=5min)
                │
            Return (from_cache=False)
```

Cache key format:
```
feed:{category}:{active_only}:{limit}:{offset}:{skills_hash}
```

Personalised responses (with skills) use a different `skills_hash` than generic responses, so they **never collide** in cache.

---

### 4.4 Strategy Pattern (Feed Fetching)

The feed endpoint uses the **Strategy Pattern** to select the fetching algorithm at runtime without any `if/else` branching in the endpoint handler.

```
FeedFetchStrategy (ABC)
        │
        ├── RelevanceFetchStrategy   ← used when skills are provided
        │     Fetches ALL items → scores → sorts globally → paginates
        │
        └── DefaultFetchStrategy     ← used when no skills provided
              Standard paginated DB fetch, no scoring
```

**Strategy selection (one line):**
```python
strategy: FeedFetchStrategy = (
    RelevanceFetchStrategy() if skill_set else DefaultFetchStrategy()
)
result = strategy.execute(...)
```

Adding a new ranking strategy (e.g., `DateSortStrategy`) requires **zero changes** to the endpoint — just a new class.

---

### 4.5 Facade Pattern (API Gateway)

The Next.js API routes act as a **Facade** — the browser never calls the FastAPI backend directly. All requests go through `/pages/api/` or `app/api/` routes which:

1. Forward requests to the FastAPI backend.
2. Inject the user's JWT from the server-side cookie.
3. Hide internal backend URLs from the browser.

---

## 5. Project Structure

```
SE_PROJECT_3_18/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point, lifespan, CORS
│   │   ├── config.py                # Settings (env vars via pydantic-settings)
│   │   ├── db.py                    # SQLAlchemy engine + session factory
│   │   ├── models/                  # ORM table definitions
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   └── rss_item.py          # NormalizedRssItem, RssAggregationResponse
│   │   ├── repositories/            # DB query functions (no business logic)
│   │   ├── routers/
│   │   │   ├── auth.py              # /auth/register, /auth/login, /auth/me
│   │   │   ├── feeds.py             # /api/feeds/rss  (Strategy + Cache-Aside)
│   │   │   └── profile.py           # /profile/upload-resume, /profile/me
│   │   ├── services/
│   │   │   ├── redis_cache.py       # Redis client wrapper (get/set/delete)
│   │   │   └── rss/
│   │   │       ├── cache_service.py # Feed-level cache orchestration
│   │   │       └── feed_sources.py  # FEED_SOURCES list (all RSS URLs + categories)
│   │   ├── workers/
│   │   │   ├── rss_refresh_worker.py   # Background RSS ingestion loop
│   │   │   └── ingestion_worker.py     # Redis invalidation after ingestion
│   │   ├── middleware/              # Custom FastAPI middleware
│   │   └── utils/                   # Shared helpers (e.g., JWT, hashing)
│   ├── requirements.txt
│   └── tests/                       # pytest test suites
│
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router pages
│   │   └── components/              # Reusable UI components
│   ├── package.json
│   └── next.config.ts
│
├── docker-compose.yml               # PostgreSQL + Redis + RSS-Bridge
├── .gitignore
└── README.md
```

---

## 6. Prerequisites

Ensure the following are installed on your machine before proceeding:

| Tool | Minimum Version | Purpose |
|---|---|---|
| [Python](https://www.python.org/downloads/) | 3.11+ | Backend runtime |
| [Node.js](https://nodejs.org/) | 18+ | Frontend runtime |
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Latest | PostgreSQL + Redis |
| [Git](https://git-scm.com/) | Latest | Version control |

---

## 7. Setup & Installation

### 7.1 Clone the Repository

```bash
git clone https://github.com/Nikhilesh4/SE_PROJECT_3_18.git
cd SE_PROJECT_3_18
```

---

### 7.2 Start Infrastructure (Docker)

Spin up **PostgreSQL**, **Redis**, and **RSS-Bridge** with a single command:

```bash
docker compose up -d
```

Verify all containers are running:

```bash
docker compose ps
```

Expected output:
```
NAME                       STATUS
unicompass-postgres        Up
unicompass-redis           Up
unicompass-rss-bridge      Up
```

> **Note**: PostgreSQL is exposed on `localhost:5432`, Redis on `localhost:6379`, and RSS-Bridge on `localhost:3000`.

---

### 7.3 Backend Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables (see Section 8)
copy .env.local.example .env.local   # Windows
# cp .env.local.example .env.local   # macOS/Linux

# 5. Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: **http://localhost:8000**  
Interactive docs (Swagger UI): **http://localhost:8000/docs**

---

### 7.4 Frontend Setup

```bash
# 1. Navigate to the frontend directory (from project root)
cd frontend

# 2. Install Node.js dependencies
npm install

# 3. Start the development server
npm run dev
```

The frontend will be available at: **http://localhost:3001** (or `3000` if RSS-Bridge is not running).

---

## 8. Environment Variables

Create a `.env.local` file inside `backend/` with the following variables:

```env
# ── Database ──────────────────────────────────────────────
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/unicompass

# ── Redis ─────────────────────────────────────────────────
REDIS_URL=redis://localhost:6379

# ── JWT Auth ──────────────────────────────────────────────
SECRET_KEY=your-super-secret-key-change-this-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Google Generative AI (Gemini) ─────────────────────────
GOOGLE_API_KEY=your-google-ai-api-key
```

> **⚠️ Warning**: Never commit `.env.local` to version control. It is already listed in `.gitignore`.

**Getting a Google API Key:**
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **"Create API Key"**
3. Copy the key and paste it as `GOOGLE_API_KEY` above.

---

## 9. Running the Application

After completing setup, run both services in separate terminals:

**Terminal 1 — Backend:**
```bash
cd backend
venv\Scripts\activate        # Windows
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

| Service | URL |
|---|---|
| Frontend (Next.js) | http://localhost:3001 |
| Backend API | http://localhost:8000 |
| Swagger / OpenAPI Docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

---

## 10. API Reference

All endpoints are prefixed with `/api` (via the FastAPI router). Full interactive docs are at `http://localhost:8000/docs`.

### 10.1 Authentication

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Register a new user account |
| `POST` | `/auth/login` | Login and receive a JWT access token |
| `GET` | `/auth/me` | Get the currently authenticated user |

**Register body:**
```json
{
  "email": "student@university.edu",
  "password": "SecurePassword123"
}
```

**Login response:**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

---

### 10.2 Feeds

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/feeds/rss` | List opportunities (paginated, optionally skill-ranked) |
| `GET` | `/api/feeds/rss/{item_id}` | Fetch a single opportunity by GUID or URL |
| `GET` | `/api/feeds/rss/summary` | Feed source statistics by category |
| `GET` | `/api/feeds/rss/cache-status` | Redis cache health and statistics |
| `POST` | `/api/feeds/rss/refresh` | Manually trigger a background RSS refresh |

**`GET /api/feeds/rss` — Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | Max items per page (1–500) |
| `offset` | int | 0 | Pagination offset |
| `category` | string | null | Filter: `internships`, `jobs`, `hackathons`, `research` |
| `active_only` | bool | true | Only return non-expired opportunities |
| `skills` | string | null | Comma-separated skills (activates relevance ranking) |
| `limit_per_feed` | int | null | Override `limit` for per-feed caps |

**Example — skill-ranked internships:**
```
GET /api/feeds/rss?category=internships&skills=python,machine+learning,fastapi&limit=20
```

**Response schema:**
```json
{
  "items": [...],
  "sources": [...],
  "total_items": 342,
  "fetched_at": "2026-04-23T08:30:00Z",
  "from_cache": true
}
```

---

### 10.3 Profile

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/profile/upload-resume` | Upload a PDF resume; AI extracts skills |
| `GET` | `/profile/me` | Get the current user's profile and extracted skills |
| `PATCH` | `/profile/me` | Update profile fields manually |

---

## 11. Design Patterns Reference

| Pattern | Where Used | File |
|---|---|---|
| **Strategy** | Feed fetching algorithm (`RelevanceFetchStrategy` vs `DefaultFetchStrategy`) | `backend/app/routers/feeds.py` |
| **Cache-Aside** | Redis read-through caching for all feed and item endpoints | `backend/app/routers/feeds.py`, `backend/app/services/redis_cache.py` |
| **Facade** | Next.js API routes hide the FastAPI backend from the browser | `frontend/src/app/api/` |
| **Repository** | Database access abstracted behind query functions | `backend/app/repositories/` |
| **Factory / Builder** | Pydantic schema construction for normalised RSS items | `backend/app/schemas/rss_item.py` |
| **Observer (async)** | Background workers emit events after ingestion | `backend/app/workers/` |

---

## 12. Code Documentation Guide

All source files follow these documentation conventions:

### Module-level docstrings (`feeds.py` example)
```python
"""HTTP API for cached RSS opportunities and feed-source metadata.

Architecture Patterns Used:
  - Cache-Aside Pattern: Redis sits in front of PostgreSQL.
  - Facade Pattern: Single entry point for all feed operations.
  - Strategy Pattern: FeedFetchStrategy (ABC) with RelevanceFetchStrategy
    and DefaultFetchStrategy concrete implementations, selected at runtime.

Architecture Tactics:
  - Performance: Redis TTL of 5 minutes reduces DB reads.
  - Availability: Redis failures fall back to DB silently.
  - Modifiability: Skills-hash keeps personalised/generic caches independent.
"""
```

### Class docstrings (Strategy Pattern)
```python
class RelevanceFetchStrategy(FeedFetchStrategy):
    """
    Relevance mode: fetch ALL items, score each one against the user's skill
    set, sort globally by score DESC, then apply pagination in Python.
    This guarantees the most relevant items surface regardless of DB page.
    """
```

### Function docstrings (scoring logic)
```python
def _relevance_score(item: NormalizedRssItem, skill_set: set[str]) -> int:
    """
    Compute relevance of an opportunity against the user's skill/interest set.

    Scoring weights (additive):
      +4  per skill found in tags         (most specific — curated metadata)
      +2  per skill found in title words  (strong signal — headline match)
      +1  per skill found in summary text (weak signal — body mention)
    """
```

### Inline section separators
```python
# ── Cache-Aside: check Redis first ───────────────────────────────────────
# ── Cache MISS: select and execute the appropriate strategy ─────────────
# ── Store in Redis ────────────────────────────────────────────────────────
```

> All non-trivial logic is explained with inline comments. Public functions and classes always have docstrings. Private helpers (prefixed `_`) document their intent briefly.

---

## 13. Testing

### Running Backend Tests

```bash
cd backend
venv\Scripts\activate    # Windows
pytest tests/ -v
```

### Running a Quick Smoke Test

```bash
# Test the feed endpoint directly
curl http://localhost:8000/api/feeds/rss?limit=5

# Test skill-ranked mode
curl "http://localhost:8000/api/feeds/rss?skills=python,react&limit=5"

# Check cache status
curl http://localhost:8000/api/feeds/rss/cache-status

# Health check
curl http://localhost:8000/health
```

### Cache Behaviour Verification

1. Make a request to `/api/feeds/rss` — observe `"from_cache": false`
2. Make the **same** request again — observe `"from_cache": true` (served from Redis in < 5 ms)
3. The cache TTL is 5 minutes (`_FEED_TTL = 300`); after expiry, the next request will re-populate Redis.

---

## 14. Contributing

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Follow code conventions**:
   - All new functions must have docstrings.
   - Add inline comments for non-obvious logic.
   - New fetch strategies must extend `FeedFetchStrategy(ABC)`.

3. **Test your changes** before submitting a PR:
   ```bash
   pytest tests/ -v
   ```

4. **Open a Pull Request** against `main` with a clear description of what changed and why.

---

