# UniCompass — Task 7: Integration, Testing & Architecture Report

> **Course**: Software Engineering (3-2)  
> **Task**: 7 — End-to-End Integration, Caching Verification, and System Documentation

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [End-to-End User Flow](#2-end-to-end-user-flow)
3. [Architecture Patterns Applied](#3-architecture-patterns-applied)
4. [Design Patterns Applied](#4-design-patterns-applied)
5. [Architectural Tactics Applied](#5-architectural-tactics-applied)
6. [Caching Architecture — Deep Dive](#6-caching-architecture--deep-dive)
7. [Skill-Based Relevance Pipeline](#7-skill-based-relevance-pipeline)
8. [Setup Instructions](#8-setup-instructions)
9. [Environment Variables](#9-environment-variables)
10. [Verification Checklist](#10-verification-checklist)
11. [Known Design Trade-offs](#11-known-design-trade-offs)

---

## 1. System Overview

**UniCompass** is an AI-powered opportunity discovery platform for university students. It aggregates internships, hackathons, research positions, and online courses from RSS feeds and job APIs, then personalises results using skills extracted from the user's uploaded resume.

### Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Frontend | Next.js 14 (App Router) | UI, server-side API proxy |
| Backend | FastAPI (Python 3.11) | REST API, business logic |
| Database | PostgreSQL + pgvector | Persistent storage |
| Cache | Redis 7 | Performance caching layer |
| AI | Google Gemini / Groq | Resume parsing |
| Container | Docker Compose | Local dev orchestration |

---

## 2. End-to-End User Flow

The full pipeline implemented in Task 7:

```
[Register] ──auto-login──▶ [Profile Page] ──upload PDF──▶ [AI Extraction]
     │                                                           │
     │                                              skills/interests saved to DB
     │                                                           │
     └──────────────────────────────────────────────────▶ [Feed Page]
                                                               │
                                              ┌────────────────┴──────────────────┐
                                              │                                   │
                                    [Generic Feed]                [Relevant-to-You Feed]
                                    (no skills param)           (skills param → backend
                                                                 re-ranks by overlap)
```

### Step-by-Step

| Step | Action | Backend | Cache Behaviour |
|------|--------|---------|----------------|
| 1 | User fills registration form | `POST /auth/register` — creates user, issues JWT | — |
| 2 | Auto-login, redirect to `/profile?new=true` | JWT stored in localStorage + cookie | — |
| 3 | Profile page loads, tries to fetch existing profile | `GET /profile/me` → 404 (no resume yet) | Cache MISS (key `profile:{id}`) |
| 4 | User uploads PDF resume | `POST /profile/upload-resume` → AI parses → saves to DB → **deletes** `profile:{id}` from Redis | Cache INVALIDATED |
| 5 | Next `GET /profile/me` | Returns fresh data from DB | Cache MISS → sets `profile:{id}` with 1h TTL |
| 6 | Subsequent `GET /profile/me` | — | **Cache HIT** — ⚡ Redis serves in <5ms |
| 7 | User navigates to `/feed` | `GET /api/feeds/rss` | Cache MISS → sets `feed:None:true:50:0:none` with 5min TTL |
| 8 | User refreshes feed | — | **Cache HIT** — ⚡ Redis |
| 9 | User clicks "Sort by Relevance" | `GET /api/feeds/rss?skills=python,ml,...` | Cache MISS for `feed:...:a1b2c3d4` (skills hash) → ranked results stored |
| 10 | Second relevance fetch | — | **Cache HIT** for the personalised key |
| 11 | User uploads new resume | `POST /profile/upload-resume` | Profile cache invalidated; feed cache expires naturally at 5min TTL |

---

## 3. Architecture Patterns Applied

### 3.1 Layered Architecture (N-Tier)

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

### 3.2 Event-Driven Architecture (Background Workers)

Two background asyncio tasks run continuously:

- **`rss_refresh_loop`** — fetches all RSS sources every N minutes and upserts into the `rss_items` table.
- **`ingestion_loop`** — after each batch ingestion, invalidates all `feed:*` keys in Redis, ensuring users never see stale data after a refresh.

This decouples feed fetching from the HTTP request path — the API never blocks on network I/O to RSS sources.

```
                        Event: "refresh complete"
[RSS Worker] ──────────────────────────────────▶ [Ingestion Worker]
                                                        │
                                              redis_cache.delete_pattern("feed:*")
```

### 3.3 Cache-Aside Pattern (Read-Through Variant)

Used on every read endpoint:

```python
# 1. Check Redis
cached = redis_cache.get(cache_key)
if cached:
    return cached  # Cache HIT

# 2. Read from DB (cache MISS)
result = repository.get(...)

# 3. Populate Redis for next request
redis_cache.set(cache_key, result, ttl=300)
return result
```

**Cache keys**:
| Resource | Redis Key | TTL |
|----------|-----------|-----|
| Feed (generic) | `feed:{category}:{active}:{limit}:{offset}:none` | 5 min |
| Feed (personalised) | `feed:{category}:{active}:{limit}:{offset}:{skills_hash}` | 5 min |
| Single item | `opportunity:{item_id}` | 30 min |
| User profile | `profile:{user_id}` | 1 hour |

**Why separate keys for personalised vs. generic?**  
If we used the same key, a generic fetch would overwrite the ranked data (or vice versa). The MD5 hash of the sorted skills list is appended — only 8 hex characters, so keys stay short.

---

## 4. Design Patterns Applied

### 4.1 Singleton Pattern — Redis Cache Service

`redis_cache.py` exposes a **single module-level instance** of `RedisCacheService`:

```python
# redis_cache.py
class RedisCacheService:
    def __init__(self):
        self._client = None  # Lazy initialisation

# Single shared instance used everywhere
redis_cache = RedisCacheService()
```

**Benefit**: No duplicate connections; the lazy init means Redis is only contacted when the first endpoint is called, not at import time.

### 4.2 Repository Pattern — Data Access Abstraction

`ProfileRepository` and `RssItemRepository` isolate all SQLAlchemy queries. Routers and services never write SQL directly.

```python
# profile_repository.py
class ProfileRepository:
    def upsert_profile(self, db, user_id, raw_text, parsed_profile): ...
    def get_by_user_id(self, db, user_id): ...
```

**Benefit**: If we migrate from PostgreSQL to another DB, only the repository layer changes.

### 4.3 Adapter Pattern — AI Service Integration

`AIProfileAdapter` wraps two AI providers (Groq → Gemini fallback) behind a uniform `structure(text) -> ProfileStructured` interface. The resume service calls the adapter without knowing which AI provider is active.

```python
class AIProfileAdapter:
    async def structure(self, raw_text: str) -> ProfileStructured:
        try:
            return await self._call_groq(raw_text)
        except Exception:
            return await self._call_gemini(raw_text)   # fallback
```

**Benefit**: New AI providers can be added by creating a new adapter without touching the service or router.

### 4.4 Strategy Pattern — Relevance Ranking

The relevance scoring algorithm is an isolated function injected conditionally into the feed endpoint:

```python
def _relevance_score(item, skill_set) -> int:
    tag_overlap   = len({t.lower() for t in item.tags} & skill_set)
    title_overlap = len({w.lower() for w in item.title.split()} & skill_set)
    return tag_overlap * 2 + title_overlap

# Applied only when skills are present (Strategy injection)
if skill_set and result.items:
    result.items = sorted(result.items, key=lambda i: _relevance_score(i, skill_set), reverse=True)
```

**Benefit**: The scoring strategy can be replaced with a more sophisticated ML model without changing the router structure.

### 4.5 Facade Pattern — Next.js API Proxy

The Next.js API route `/api/feeds` acts as a **Facade** — the frontend never communicates directly with FastAPI. It hides the backend URL, forwards only whitelisted parameters, and adds auth headers.

```
[React Component] → [/api/feeds (Next.js)] → [FastAPI /api/feeds/rss]
                          (Facade)
```

### 4.6 Data Transfer Object (DTO) — Registration Response

The `RegisterResponse` schema extends `UserResponse` with `access_token`, creating a DTO that carries exactly the data the client needs without exposing internal fields:

```python
class RegisterResponse(UserResponse):
    access_token: str
```

---

## 5. Architectural Tactics Applied

### 5.1 Performance Tactics

| Tactic | Where Applied | Effect |
|--------|--------------|--------|
| **Caching** | Redis in front of every read | Reduces DB queries from O(request_rate) to ~1 per TTL window |
| **Client-side caching** | `localStorage` in `useFeed.ts` | Instant re-render on navigation without network round-trip |
| **Lazy connection** | Redis client in `RedisCacheService` | No connection overhead at startup |
| **Background refresh** | `rss_refresh_loop` worker | RSS network I/O moved completely off the request path |
| **Pagination** | Offset + limit on feed API | Limits DB scan to ≤500 rows per query |

**Measured impact** (approximated):
- Feed endpoint: **first request** ~120-200ms (DB query + Redis SET); **subsequent** ~5-15ms (Redis GET)
- Profile endpoint: **first request** ~50ms; **subsequent** ~3ms

### 5.2 Availability Tactics

| Tactic | Where Applied |
|--------|--------------|
| **Graceful degradation** | All `redis_cache.get/set` calls wrapped in `try/except` — Redis failure falls back to DB |
| **Timeout** | Redis connections have `socket_connect_timeout=2s` and `socket_timeout=2s` |
| **Health endpoint** | `GET /health` always returns 200 regardless of Redis/DB state |
| **Error boundaries** | Frontend shows error state with retry button — never a blank screen |

### 5.3 Modifiability Tactics

| Tactic | Where Applied |
|--------|--------------|
| **Separation of concerns** | 5-layer architecture — each layer has one responsibility |
| **Abstract interfaces** | `AIProfileAdapter` hides provider details |
| **Configuration externalisation** | All secrets in `.env.local` / Docker env — no hardcoded values |
| **Cache key namespacing** | `feed:*`, `profile:*`, `opportunity:*` — bulk invalidation per namespace |

### 5.4 Security Tactics

| Tactic | Where Applied |
|--------|--------------|
| **JWT authentication** | All profile and feed (personalised) endpoints require Bearer token |
| **bcrypt hashing** | Passwords never stored in plaintext |
| **Input validation** | Pydantic schemas validate all request bodies |
| **CORS restriction** | Only whitelisted origins allowed |
| **File validation** | PDF magic-bytes check (`%PDF`) + 5MB size limit on resume upload |

---

## 6. Caching Architecture — Deep Dive

### Redis Key Lifecycle

```
Request arrives
      │
      ▼
redis_cache.get(key)
      │
      ├─── HIT ──▶ Deserialise JSON → Set from_cache=True → Return (≈5ms)
      │
      └─── MISS ─▶ Query PostgreSQL (≈50-200ms)
                         │
                         ▼
                   redis_cache.set(key, data, ttl)
                         │
                         ▼
                   Set from_cache=False → Return
```

### The `from_cache` Flag

The `from_cache` boolean is intentionally **never stored in Redis**. It is set dynamically after deserialisation:

```python
# Cache HIT path
response = RssAggregationResponse(**cached)
response.from_cache = True   # set after deserialisation

# Cache MISS path
redis_cache.set(cache_key, result.model_dump(mode="json"), ttl_seconds=300)
result.from_cache = False    # set after storing (never in Redis)
```

This ensures the cached JSON never contains `from_cache: true`, which would incorrectly propagate if the JSON were used directly.

### Cache Invalidation Rules

| Event | Keys Invalidated | Method |
|-------|-----------------|--------|
| Resume uploaded | `profile:{user_id}` | Exact key `DELETE` |
| RSS ingestion completes | `feed:*` | Pattern `SCAN + DELETE` |
| Manual refresh triggered | `feed:{category}:*` or `feed:*` | Pattern `SCAN + DELETE` |

### Skills-Personalised Caching

When a user enables "Sort by Relevance":

```
Skills: ["Python", "Machine Learning", "React"]
Normalised + sorted: ["machine learning", "python", "react"]
Joined: "machine learning,python,react"
MD5[:8]: "a1b2c3d4"

Cache key: "feed:None:true:50:0:a1b2c3d4"
```

Two users with identical skills get the same cache key — maximising cache reuse. Different skill sets get separate keys — no pollution between users.

---

## 7. Skill-Based Relevance Pipeline

```
[User uploads resume]
        │
        ▼
[AI extracts skills + interests from PDF text]
  e.g., skills: ["Python", "React", "SQL"]
        interests: ["Machine Learning", "Web Dev"]
        │
        ▼
[Saved to UserProfile table in PostgreSQL]
        │
        ▼
[Profile cache invalidated: DEL profile:{user_id}]
        │
[User visits feed, clicks "Sort by Relevance"]
        │
        ▼
[useProfile hook fetches GET /profile/me]
  → skills + interests returned (from Redis after first hit)
        │
        ▼
[useFeed passes skills=python,react,sql,... to /api/feeds]
        │
        ▼
[Next.js proxy forwards to GET /api/feeds/rss?skills=...]
        │
        ▼
[FastAPI computes skills_hash, checks Redis]
  MISS → fetch from DB
        │
        ▼
[_relevance_score() computes: 2*tag_overlap + title_overlap for each item]
        │
        ▼
[Items sorted descending by score, then by published_at]
        │
        ▼
[Result cached under feed:...:a1b2c3d4 for 5 min]
        │
        ▼
[Frontend renders: matched tags highlighted in violet, "🎯 Match" badge on cards]
```

---

## 8. Setup Instructions

### Prerequisites

- Docker Desktop (or Docker Engine + Compose)
- Node.js ≥ 18
- Python ≥ 3.11 (optional — Docker handles it)

### 1. Clone and configure

```bash
git clone https://github.com/Nikhilesh4/SE_PROJECT_3_18.git
cd SE_PROJECT_3_18
```

### 2. Backend environment

Create `backend/.env.local`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/unicompass
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=10080
GEMINI_API_KEY=your-google-gemini-key
GROQ_API_KEY=your-groq-key
```

### 3. Frontend environment

Create `frontend/.env.local`:

```env
BACKEND_URL=http://localhost:8000
```

### 4. Start services with Docker

```bash
docker-compose up --build
```

This starts:
- PostgreSQL on port 5432
- Redis on port 6379
- FastAPI backend on port 8000
- (Frontend started separately)

### 5. Start frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:3000**

### 6. Verify services

```bash
# Backend health
curl http://localhost:8000/health

# Redis ping
docker exec -it <redis-container> redis-cli ping

# Feed API
curl http://localhost:8000/api/feeds/rss
```

---

## 9. Environment Variables

| Variable | Service | Required | Description |
|----------|---------|----------|-------------|
| `DATABASE_URL` | Backend | ✅ | PostgreSQL connection string |
| `REDIS_URL` | Backend | ✅ | Redis connection URL |
| `SECRET_KEY` | Backend | ✅ | JWT signing secret (≥32 chars) |
| `ALGORITHM` | Backend | ✅ | JWT algorithm (`HS256`) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Backend | ✅ | Token TTL in minutes |
| `GEMINI_API_KEY` | Backend | ✅ | Google AI API key for resume parsing |
| `GROQ_API_KEY` | Backend | ⚠️ | Groq key (optional — Gemini is fallback) |
| `BACKEND_URL` | Frontend | ✅ | Internal backend URL for Next.js proxy |

---

## 10. Verification Checklist

### Pipeline Verification

- [ ] Register a new user → browser redirects to `/profile?new=true` (not `/login`)
- [ ] Welcome hero is shown with 3-step progress indicator
- [ ] Upload a resume PDF → "Extracting using Groq AI…" shows → profile appears
- [ ] Post-upload CTA "Explore Your Feed →" is shown in green banner
- [ ] Navigate to Feed → data badge shows "🗄️ PostgreSQL DB" (cache miss)
- [ ] Refresh feed → badge changes to "⚡ Redis Cache" (cache hit)
- [ ] Click "Sort by Relevance" → button turns violet, skill chips appear
- [ ] Cards with matching tags show "🎯 Match" badge and violet border
- [ ] Re-upload resume → profile badge shows "🗄️ PostgreSQL DB" (cache invalidated)
- [ ] Wait 5 minutes → feed badge returns to "🗄️ PostgreSQL DB" (TTL expired)

### Cache Verification (Backend Logs)

```
INFO  Redis SET key='feed:None:true:50:0:none' ttl=300s   ← first feed request
DEBUG Redis GET hit for key='feed:None:true:50:0:none'    ← second request
INFO  Redis DEL key='profile:3'                           ← after resume upload
INFO  Redis SET key='feed:None:true:50:0:a1b2c3d4' ttl=300s ← personalised fetch
```

---

## 11. Known Design Trade-offs

| Decision | Trade-off |
|----------|-----------|
| **Skills-based ranking is server-side** | More backend compute, but allows Redis caching of ranked results; client-side ranking would not benefit from caching |
| **Feed cache TTL is 5 minutes** | Stale data for up to 5 min after new listings appear; shorter TTL = more DB load |
| **Profile cache TTL is 1 hour** | If AI re-parses with different results (rare), users see old data for up to 1 hour — but profile only changes on explicit re-upload |
| **MD5 skills hash for cache key** | Tiny collision probability (8-hex = 1/4B); acceptable for this use case |
| **No background profile pre-warming** | Profile is fetched on-demand (Cache-Aside); a write-through strategy on upload would pre-warm but adds complexity |
| **`from_cache` is a UI hint, not security control** | It can be faked by the client; it is purely for observability/demonstration |