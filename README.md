# 🧭 UniCompass

> **AI-powered, agentic opportunity discovery platform** — internships, jobs, hackathons, research and open-source programs gathered from RSS, job APIs, ATS boards and discovery agents, ranked semantically against your resume, and backed by an AI assistant, RAG over posting text, an MCP server, an application tracker and live alerts.

> **Status and future plans:** see [`docs/AGENTIC_ROADMAP.md`](docs/AGENTIC_ROADMAP.md).

---

## 📑 Table of Contents

- [🧭 UniCompass](#-unicompass)
  - [📑 Table of Contents](#-table-of-contents)
  - [1. Project Overview](#1-project-overview)
  - [2. Features](#2-features)
  - [3. Tech Stack](#3-tech-stack)
    - [Backend](#backend)
    - [Frontend](#frontend)
    - [Infrastructure](#infrastructure)
  - [4. Architecture Overview](#4-architecture-overview)
    - [4.1 Layered Architecture](#41-layered-architecture)
    - [4.2 Event-Driven Background Workers](#42-event-driven-background-workers)
    - [4.3 Cache-Aside Pattern (Redis)](#43-cache-aside-pattern-redis)
    - [4.4 Strategy Pattern (Feed Fetching)](#44-strategy-pattern-feed-fetching)
    - [4.5 Facade Pattern (API Gateway)](#45-facade-pattern-api-gateway)
    - [4.6 Compass Assistant (Agent)](#46-compass-assistant-agent)
    - [4.7 RAG over posting text](#47-rag-over-posting-text)
  - [5. Project Structure](#5-project-structure)
  - [6. Prerequisites](#6-prerequisites)
  - [7. Setup \& Installation](#7-setup--installation)
    - [7.1 Clone the Repository](#71-clone-the-repository)
    - [7.2 Start Infrastructure (Docker)](#72-start-infrastructure-docker)
    - [7.3 Backend Setup](#73-backend-setup)
    - [7.4 Frontend Setup](#74-frontend-setup)
  - [8. Environment Variables](#8-environment-variables)
  - [9. Running the Application](#9-running-the-application)
  - [10. API Reference](#10-api-reference)
    - [10.1 Authentication](#101-authentication)
    - [10.2 Feeds](#102-feeds)
    - [10.3 Profile](#103-profile)
    - [10.4 RAG (posting text)](#104-rag-posting-text)
  - [11. Design Patterns Reference](#11-design-patterns-reference)
  - [12. Code Documentation Guide](#12-code-documentation-guide)
    - [Module-level docstrings (`feeds.py` example)](#module-level-docstrings-feedspy-example)
    - [Class docstrings (Strategy Pattern)](#class-docstrings-strategy-pattern)
    - [Function docstrings (scoring logic)](#function-docstrings-scoring-logic)
    - [Inline section separators](#inline-section-separators)
  - [13. Testing](#13-testing)
    - [Running Backend Tests](#running-backend-tests)
    - [Running a Quick Smoke Test](#running-a-quick-smoke-test)
    - [Cache Behaviour Verification](#cache-behaviour-verification)
  - [14. Contributing](#14-contributing)

---

## 1. Project Overview

**UniCompass** is a full-stack web application that helps university students discover curated opportunities — internships, jobs, hackathons, and research positions — all in one place.

Background workers ingest RSS/Atom feeds, job APIs (Adzuna, Jooble) and discovery channels (Greenhouse/Lever/Ashby/Workable/SmartRecruiters boards, HN "Who's Hiring", Devpost, arXiv/Semantic Scholar, GSoC/Outreachy/LFX/MLH), normalise them into one schema, clean out junk with versioned QA rules, and store them in PostgreSQL with pgvector embeddings. When a user uploads a resume, an LLM extracts their skills and the feed is ranked by a hybrid of semantic similarity and keyword matches, adjusted by their feedback.

On top of that, students get a streaming AI assistant, cited answers about any posting (RAG), saved-search Missions with live notifications, a Kanban application tracker, a weekly career standup, and insights on skill demand and pay. Everything is also available to Claude Desktop, Claude Code or Cursor through a 30-tool MCP server.

Redis is used as a read-through cache (Cache-Aside Pattern) with a 5-minute TTL, so repeated requests to the same endpoint are served in < 5 ms without touching the database.

---

## 2. Features

| Feature | Description |
|---|---|
| 🔐 **Authentication** | JWT-based login/register with bcrypt password hashing |
| 📄 **Resume Parsing** | Upload a PDF resume; an LLM (Groq by default, Gemini optional) extracts skills automatically |
| 🔍 **Semantic Skill Matching** | Feed items are ranked by meaning, not just keywords: pgvector cosine similarity on `all-MiniLM-L6-v2` embeddings, blended with keyword matches ("machine learning" finds a "neural networks" posting) |
| ⚡ **Redis Caching** | Cache-Aside with per-user skill-hash keys; cold-start < 200 ms, warm < 5 ms |
| 🔄 **Background Workers** | RSS refresh, ingestion, embedding/RAG indexing, discovery and activity workers; run inside the API in dev or in a separate `worker` container with Docker Compose |
| 📊 **Cache Observability** | Every API response includes a `from_cache` flag for transparency |
| 🗂️ **Search and Filters** | Server-side full-text search (websearch syntax) with category, source, remote, minimum stipend and closing-soon filters |
| 📚 **Posting Q&A (RAG)** | Ask a posting "is it paid?" or "who can apply?" and get an answer that cites the passages it comes from, or says the posting doesn't state it. Also cross-posting fact search, side-by-side comparison, and resume-to-posting matching (via the assistant and MCP) |
| 💬 **Compass Assistant** | In-app AI chat at `/assistant` that searches, explains and bookmarks opportunities and checks deadlines, using the same tools as the MCP server. Runs on Groq (default) or Claude |
| 🤖 **MCP Server** | Use UniCompass from Claude Desktop / Claude Code / Cursor: 30 tools (search, RAG, ATS resume check, bookmarks, applications, missions, insights, coach, standup, pay insights), 2 resources and 3 prompts. See [`mcp-server/README.md`](mcp-server/README.md) |
| 🛰️ **Discovery Agents** | ATS boards, HN "Who's Hiring" (LLM extraction), Devpost, scholarly sources, open-source programs, web search (Tavily/Brave) and a Source Scout that proposes new feeds for admin approval |
| 🧹 **Ingestion QA** | Versioned, explainable rules hide error pages, podcasts, listicles, news and recaps from every discovery surface; each rejection is flagged and reversible |
| 🎯 **Missions and Alerts** | Saved natural-language searches run on a schedule; new matches arrive in a navbar bell over Server-Sent Events, plus a weekly digest |
| 📋 **Application Tracker** | Kanban board (saved → applied → interview → offer/rejected) with notes, deadline view and `.ics` calendar export |
| 🗓️ **Career Standup** | Up to three ranked actions for the week (deadlines, interviews, stale applications, missing skills) in the Applications tab of your profile, via the API and the assistant |
| 📈 **Insights** | Explainable ranking, scam/eligibility/remote signals, skill-demand trends, company briefs, project suggestions, and pay insights (medians and ranges by category with sample sizes) |
| 🧑‍🏫 **Coach** | Outreach drafts, research-lab scout, mock interview questions with feedback, and memory search over your own notes |
| 🔐 **Security** | httpOnly cookie session via Next.js proxy routes, secret-key validation at startup, rate limits on login, register and resume upload |

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
| LLMs | Groq (`openai/gpt-oss-120b`, default) or Anthropic Claude for the assistant and RAG; Gemini optional for resume parsing |
| Embeddings | `all-MiniLM-L6-v2` via [fastembed](https://github.com/qdrant/fastembed) (ONNX), stored in pgvector |
| Agents / MCP | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) (server and client), custom tool-calling loop |
| Migrations | [Alembic](https://alembic.sqlalchemy.org/) |
| RSS Parsing | [feedparser](https://feedparser.readthedocs.io/) |
| PDF Parsing | [PyMuPDF](https://pymupdf.readthedocs.io/) |

### Frontend
| Layer | Technology |
|---|---|
| Framework | [Next.js 16](https://nextjs.org/) (App Router) |
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

Background `asyncio` workers (`backend/app/workers/`) run inside the FastAPI lifespan by default (`RUN_WORKERS_IN_API=true`), or in a separate `worker` container (`python -m app.worker_main`) under Docker Compose:

- **`rss_refresh_worker`** — Fetches all RSS sources every N minutes and upserts into the `rss_items` table.
- **`ingestion_worker`** — After each ingestion batch, invalidates all `feed:*` keys in Redis, ensuring users never see stale data after a refresh.
- **`embedding_worker`** — Embeds new or changed postings and (re)builds their RAG passages; backfills older rows.
- **`discovery_worker`** — Runs the discovery pipeline (ATS, HN, Devpost, scholarly, programs, web search): extract → verify → enrich → upsert.
- **`activity_worker`** — Runs Ingestion QA first, then Missions, new-match alerts and the weekly digest.

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
feed:{category}:{active_only}:{limit}:{offset}:{skills_hash}[-semantic]
```

Personalised responses (with skills) use a different `skills_hash` than generic responses, so they **never collide** in cache. The `-semantic` suffix keeps hybrid-ranked results apart from keyword-only fallback results.

---

### 4.4 Strategy Pattern (Feed Fetching)

The feed endpoint uses the **Strategy Pattern** to select the fetching algorithm at runtime without any `if/else` branching in the endpoint handler.

```
FeedFetchStrategy (ABC)
        │
        ├── HybridRelevanceFetchStrategy ← skills provided + embedding model ready
        │     ALL items → 0.7 × cosine similarity (pgvector) + 0.3 × keyword score
        │     → sorts globally → paginates
        │
        ├── RelevanceFetchStrategy   ← skills provided, model unavailable (fallback)
        │     Fetches ALL items → keyword scores → sorts globally → paginates
        │
        └── DefaultFetchStrategy     ← used when no skills provided
              Standard paginated DB fetch, no scoring
```

**Strategy selection:**
```python
vector = query_vector(skill_list)          # None if the model isn't ready
if vector is not None:
    strategy = HybridRelevanceFetchStrategy(vector)
elif skill_set:
    strategy = RelevanceFetchStrategy()
else:
    strategy = DefaultFetchStrategy()
result = strategy.execute(...)
```

**How embeddings are produced.** A third background worker (`workers/embedding_worker.py`)
loads the model once (the first start downloads about 90 MB into `backend/.cache/fastembed`), then every
minute embeds every `rss_items` row and profile whose vector is `NULL`. That covers new items
from all ingestion paths, backfills existing rows, and catches items whose title, summary or tags
changed, because the upsert resets their vector. Requests never wait for the model: until it is
ready, ranking falls back to keywords.

Adding a new ranking strategy (e.g., `DateSortStrategy`) requires **zero changes** to the endpoint — just a new class.

---

### 4.5 Facade Pattern (API Gateway)

The Next.js API routes act as a **Facade** — the browser never calls the FastAPI backend directly. All requests go through `/pages/api/` or `app/api/` routes which:

1. Forward requests to the FastAPI backend.
2. Inject the user's JWT from the server-side cookie.
3. Hide internal backend URLs from the browser.

---

### 4.6 Compass Assistant (Agent)

`POST /agent/chat` runs a tool-use loop and streams Server-Sent Events: text deltas, tool calls,
tool results and a final `done` event.

```
Browser ──SSE──► routers/agent.py ──► services/agent/loop.py ──► LLMProvider (Groq | Claude)
                                            │
                                            └─► Toolbox = UniCompass MCP server, in-process
                                                  └─► FastAPI app via ASGI transport,
                                                      authenticated with the chatting user's JWT
```

- **One tool definition, two consumers.** The agent's tools are the `mcp-server/` tools, so the
  in-app assistant and Claude Desktop/Cursor behave identically. Tool calls go through the normal
  API as the signed-in user, which means the agent can't do anything that user's own requests couldn't.
- **Provider adapters.** Groq uses its OpenAI-compatible streaming API. Claude uses the Anthropic SDK
  with adaptive thinking and server-side refusal fallbacks (`fallbacks="default"`).
- **Append-only history** in `agent_conversations` / `agent_messages`, stored in each provider's own
  message format. Claude needs its thinking blocks sent back unchanged, so a conversation stays on the
  provider that started it. An assistant turn and its tool results are saved together, so an
  interrupted request never leaves a tool call without a result.
- **Guardrails.** At most 8 tool rounds per message; the model then gets one turn to answer with what it
  has. Bad tool arguments, crashes and truncated or refused turns come back to the model as error
  results. The system prompt treats posting text as untrusted data.

### 4.7 RAG over posting text

Postings are split into passages of about 450 characters (sentence-packed, one sentence of overlap,
plus a `Tags:` passage) and stored in `rag_chunks` with an embedding and a generated `tsvector`.
The embedding worker builds them: when it (re-)embeds a posting it rebuilds that posting's
passages, so they follow text changes, and it backfills postings indexed before the table existed.

```
question ──► full-text (websearch_to_tsquery, GIN) ─┐
         └─► embedding ──► pgvector cosine (HNSW) ──┴─► Reciprocal Rank Fusion ──► cited passages
```

- **Across all postings** a full-text hit must contain every term; within one posting any term counts.
  Meaning-only hits below cosine 0.35 are dropped, so "nothing relevant" stays empty.
- **Without the embedding model**, retrieval falls back to full-text search alone.
- **Who writes the answer.** Retrieval returns passages; the assistant's or MCP client's own model
  writes the answer. Only the posting page's Ask box (`POST /api/rag/items/{id}/ask`) makes its own
  call to the configured agent provider, with a cite-or-say-"Not stated in this posting" prompt.
- Indexing uses only the stored summaries (capped at 2,000 characters by ingestion), so answers
  can only be as complete as the feed text.

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
│   │   │   ├── profile.py           # /profile/upload-resume, /profile/me
│   │   │   ├── agent.py             # /agent/chat (SSE), conversations
│   │   │   ├── rag.py               # /api/rag/* posting search, ask, compare
│   │   │   ├── applications.py      # tracker, deadlines, .ics, standup
│   │   │   ├── insights.py          # search, signals, trends, companies, stipends
│   │   │   ├── missions.py          # saved searches and matches
│   │   │   ├── notifications.py     # list, mark read, SSE stream
│   │   │   └── coach.py             # outreach, interview, research scout, discovery admin
│   │   ├── services/
│   │   │   ├── redis_cache.py       # Redis client wrapper (get/set/delete)
│   │   │   ├── agent/               # Compass Assistant loop, providers, toolbox, MCP clients
│   │   │   ├── rag/                 # chunking, indexing, hybrid retrieval, cited answers
│   │   │   ├── discovery/           # ATS, HN, Devpost, scholarly, programs, web search, QA rules
│   │   │   ├── insights/            # signals, explanations, .ics export
│   │   │   ├── matching/            # embeddings and hybrid ranking
│   │   │   └── rss/
│   │   │       ├── cache_service.py # Feed-level cache orchestration
│   │   │       └── feed_sources.py  # FEED_SOURCES list (all RSS URLs + categories)
│   │   ├── workers/
│   │   │   ├── rss_refresh_worker.py   # Background RSS ingestion loop
│   │   │   ├── ingestion_worker.py     # Redis invalidation after ingestion
│   │   │   ├── embedding_worker.py     # Embeddings + RAG passages
│   │   │   ├── discovery_worker.py     # Discovery pipeline
│   │   │   └── activity_worker.py      # QA, missions, alerts, digest
│   │   ├── middleware/              # Custom FastAPI middleware
│   │   └── utils/                   # Shared helpers (e.g., JWT, hashing)
│   ├── alembic/                     # database migrations (0001–0006)
│   ├── eval/                        # RAG evaluation harness
│   ├── requirements.txt
│   └── tests/                       # pytest suites (198 tests)
│
├── frontend/
│   ├── src/
│   │   ├── app/                     # Next.js App Router pages
│   │   └── components/              # Reusable UI components
│   ├── package.json
│   └── next.config.ts
│
├── mcp-server/                      # MCP server for AI assistants, 26 tests (see mcp-server/README.md)
├── docs/                            # architecture docs, ADRs, AGENTIC_ROADMAP.md
│
├── docker-compose.yml               # PostgreSQL + Redis + RSS-Bridge; `app` profile adds api + worker
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

**Database migrations (Alembic).** The schema lives in `backend/alembic/versions/`.
The API applies pending migrations on startup (`RUN_MIGRATIONS_ON_STARTUP=true` by default),
so the command above is enough for local development. Databases created before Alembic was
introduced are adopted automatically by the baseline migration. Manual commands:

```bash
alembic upgrade head                          # apply migrations
alembic revision -m "add xyz column"          # new migration (edit the generated file)
alembic revision --autogenerate -m "..."      # or diff against the models
```

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
# At least 32 characters; placeholder values are rejected at startup. If unset, a random
# key is generated into backend/.secret_key (gitignored) on first run.
# Generate one: python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

# ── Resume parsing (Groq by default; Gemini optional) ────
PROFILE_AI_PROVIDER=groq            # or "gemini"
GEMINI_API_KEY=your-gemini-key      # only needed for gemini

# ── Compass Assistant ────────────────────────────────────
AGENT_PROVIDER=groq                 # or "anthropic"
GROQ_API_KEY=your-groq-key          # used for groq (also used by resume parsing)
GROQ_MODEL=openai/gpt-oss-120b         # default; the old llama-3.3-70b-versatile default was retired by Groq
GROQ_MAX_OUTPUT_TOKENS=1500          # Groq counts this against its 8k tokens/minute free-tier limit
AGENT_TOOL_RESULT_CHARS=5000         # cap per tool result fed back to the assistant
ANTHROPIC_API_KEY=your-anthropic-key  # used for anthropic (default model claude-opus-5-5)
# AGENT_MODEL=                      # optional model override for the chosen provider

# ── Rate limiting (optional; defaults shown) ─────────────
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URI=memory://    # use your REDIS_URL when running several API processes
LOGIN_RATE_LIMIT=10/minute          # per client IP
REGISTER_RATE_LIMIT=10/hour         # per client IP
UPLOAD_RATE_LIMIT=10/hour           # per user (resume upload calls an LLM)
OTP_RATE_LIMIT=10/hour              # per client IP (signup email codes)

# ── Signup email verification (optional; defaults shown) ─
# Signup asks for a 6-digit code sent to the user's email. Without SMTP_HOST the
# code is only printed in the backend log (fine for local development).
REQUIRE_EMAIL_VERIFICATION=true
SMTP_HOST=                          # e.g. smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=                      # for Gmail use an app password
SMTP_FROM=                          # defaults to SMTP_USER
SMTP_STARTTLS=true                  # set SMTP_SSL=true instead for port 465

# ── Semantic matching (optional; defaults shown) ─────────
EMBEDDINGS_ENABLED=true
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2   # must output 384-dim vectors
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
| `PATCH` | `/profile/me` | Edit `skills` and/or `interests` (omitted fields unchanged; trimmed and de-duplicated) |

---

### 10.4 RAG (posting text)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/rag/search?q=&category=&active_only=&limit=` | Passages across all postings that state `q` |
| `GET` | `/api/rag/items/{id}/passages?q=&limit=` | Passages of one posting, most relevant to `q` first |
| `GET` | `/api/rag/compare?ids=1,2,3&aspects=pay,location` | Per-aspect passages for 2–5 postings |
| `GET` | `/api/rag/items/{id}/resume-match` | Resume lines most relevant to the posting (auth) |
| `POST` | `/api/rag/items/{id}/ask` | `{"question"}` → grounded answer with `citations` and `passages` (auth; one LLM call) |

### 10.5 Tracker, insights, missions, notifications and coach

All endpoints below are under `/api` and require auth.

| Area | Endpoints |
|---|---|
| Applications | `GET /applications`, `PATCH /applications/{item_id}` (status, notes), `GET /deadlines`, `GET /bookmarks/calendar.ics`, `GET /standup` (`?polish=true` lets the LLM reword the summary) |
| Search and insights | `GET /search`, `GET /insights/items/{item_id}` (signals, explanation, eligibility), `GET /insights/trends`, `GET /insights/projects`, `GET /insights/company`, `GET /insights/companies`, `GET /insights/stipends` |
| Feedback | `POST` / `DELETE /feedback/{item_id}`, `GET /feedback` |
| Missions | `GET` / `POST /missions`, `PATCH` / `DELETE /missions/{id}`, `POST /missions/{id}/run`, `GET /missions/{id}/matches` |
| Notifications | `GET /notifications`, `POST /notifications/read`, `GET /notifications/stream` (SSE) |
| Coach | `POST /outreach/draft`, `POST /research/scout`, `POST /interview/questions`, `POST /interview/feedback`, `GET /memory/search` |
| Discovery | `POST /discovery/run`, `GET /discovery/runs`, `POST /discovery/source-scout`, `GET /discovery/source-proposals`, `POST /discovery/source-proposals/{run_id}/approve` or `/reject` |

Workers run inside the API by default (`RUN_WORKERS_IN_API=true`). With Docker Compose they run in a
separate `worker` container (`python -m app.worker_main`). Discovery needs no key for ATS, HN, Devpost
and scholarly sources. Web search uses `TAVILY_API_KEY` or `BRAVE_API_KEY`. External MCP servers are
configured in `backend/app/services/agent/mcp_clients.json` and all ship disabled.

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

The suite runs against a real PostgreSQL (the models use `ARRAY` and pgvector) and fakes Redis.
Use a **disposable** database whose name ends in `_test`; its schema is dropped at the start of each run.

```bash
# Throwaway pgvector container on port 5433 (separate from the dev database)
docker run -d --rm --name unicompass-test-pg -p 5433:5432 \
    -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=unicompass_test pgvector/pgvector:pg16

cd backend
source venv/bin/activate          # Windows: venv\Scripts\activate
pytest -v

# Different host/port?  TEST_DATABASE_URL=postgresql://user:pass@host:port/name_test pytest
```

If the test database is unreachable, DB-backed tests are skipped (pure unit tests still run).

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
   cd backend && pytest -v                 # 198 tests, needs the test Postgres
   cd ../mcp-server && .venv/bin/pytest    # 26 tests
   cd ../frontend && npx tsc --noEmit && npx eslint
   ```

4. **Open a Pull Request** against `main` with a clear description of what changed and why.

---

