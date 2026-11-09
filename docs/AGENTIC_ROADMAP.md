# UniCompass: Agentic Roadmap and Implementation Status

> Last updated: 2026-11-10 · Branch: `agentic-roadmap` (16 commits ahead of `main`, not merged, not pushed)

This document tracks the plan to finish UniCompass and turn it into an agentic, MCP-connected
career platform: what is built, how it was verified, and what is planned next.

**Status legend:** ✅ Done and verified with a real LLM · 🟢 Done, automated tests pass, not yet run against the real external service · ⬜ Not started

---

## 1. Summary

UniCompass collects internships, jobs, hackathons, research positions, freelance work and courses
from RSS feeds, job APIs (Adzuna, Jooble), public ATS boards, HN "Who's Hiring", Devpost, scholarly
sources and open-source programs. It extracts a student's skills from their resume (Groq or Gemini),
ranks the feed for them semantically, and adds an AI assistant, RAG over posting text, an MCP server,
an application tracker, saved-search Missions with live notifications, and career insights.

The roadmap had three goals, all now met:
1. **Finish what was started:** semantic matching (FR-4), real-time notifications (FR-5), bug fixes, tests, migrations.
2. **Make it more useful:** deadline and application tracking, skill-gap analysis, explainable ranking, insights.
3. **Make it agentic:** an in-app assistant, an MCP server, RAG, and autonomous discovery agents beyond RSS.

### Progress at a glance

| Phase | What | Status | Commit |
|---|---|---|---|
| 1 | Foundation: bug fixes, Alembic, tests, editable profile | ✅ | `01c851b` |
| 2 | Semantic matching with pgvector embeddings (FR-4) | ✅ | `ef3ef2c` |
| 3 | UniCompass MCP server | ✅ | `e5ce779` |
| 4 | Compass Assistant (in-app agent, Groq) | ✅ (Anthropic provider 🟢) | `c194e01` |
| 5 | RAG over posting text | ✅ | `8842d1d` |
| G9 | Security: secret-key validation, rate limiting, httpOnly cookie session | ✅ | `2d20f39`, `c437b1b` |
| 6 | Discovery channels: ATS boards, HN, Devpost, scholarly, programs, Source Scout | ✅ (web search 🟢) | `2a83c6f` |
| 7 | Discovery pipeline, Missions, SSE notifications (G2), digest, tracker, insights, coach, worker container (G8) | ✅ | `2a83c6f`, `c437b1b` |
| 8 | External MCP clients (all ship disabled) | 🟢 tested against a fake server only | `2a83c6f` |
| — | Real-LLM fixes, per-request tool selection | ✅ | `6c5e783`, `dde6e39` |
| — | Ingestion QA v2, career standup, pay insights | ✅ | `4b17ab0`, `e065495`, `2a1277b` |

### Test status (verified 2026-11-10)

| Suite | Result | How to run |
|---|---|---|
| Backend (`backend/tests`, 22 files) | **198 passed** | see §7 |
| MCP server (`mcp-server/tests`) | **26 passed** | `cd mcp-server && .venv/bin/pytest` |
| Frontend type-check | **clean** | `cd frontend && npx tsc --noEmit` |
| Frontend lint | **1 error, 1 warning** (see §5) | `cd frontend && npx eslint` |
| Frontend tests | **none yet** | — |

---

## 2. Architecture

```
                 ┌──────────────────── Next.js frontend (:3001) ─────────────────────┐
                 │ Feed · Detail (+ Ask this posting) · Search · Applications board  │
                 │ Missions · Insights · Research · Assistant · Profile · Bell (SSE) │
                 └──────────────┬─────────────────────────────────────────────────────┘
                                │ Next.js proxy routes, httpOnly session cookie
┌──────────────────────────── FastAPI backend (:8000) ─────────────────────────────────────┐
│ routers: auth · feeds · bookmarks · profile · agent · rag · applications · insights ·    │
│          missions · notifications · coach                                                │
│ Ranking (Strategy): Hybrid (0.7·cosine + 0.3·keyword) + feedback │ Keyword │ Default     │
│ Compass Agent: loop.py ── LLMProvider (Groq | Claude) ── Toolbox (per-request tool select)│
│        ├── in-process UniCompass MCP server (30 tools, user's JWT)                       │
│        └── external MCP servers from mcp_clients.json (disabled by default)              │
│ RAG: chunking → rag_chunks (tsvector + vector) → hybrid retrieval (RRF) → cited answers  │
└──────────────┬───────────────────────────────┬───────────────────────────────────────────┘
               │                               │
    PostgreSQL 16 + pgvector              Redis 7 (cache-aside, TTL timestamps)
               ▲
┌──────────────┴─────────── worker container (python -m app.worker_main) ──────────────────┐
│ rss_refresh · ingestion · embedding + RAG indexing · discovery pipeline                  │
│ (Planner → source workers → Extractor → Verifier → Enricher → Ranker → Notifier)         │
│ activity worker: Ingestion QA → Missions → alerts → weekly digest / standup              │
└──────────────────────────────────────────────────────────────────────────────────────────┘

External assistants (Claude Desktop / Code / Cursor) ──stdio──► mcp-server/ ──HTTP──► backend
```

### Database migrations (`backend/alembic/versions/`)

| Revision | Adds |
|---|---|
| `0001_baseline` | users, profiles, rss_items, bookmarks (adopts databases created by the old `create_all`) |
| `0002_drop_opportunities` | Drops the unused `opportunities` table, only if empty |
| `0003_rss_item_embeddings` | `rss_items.embedding vector(384)` + HNSW cosine index |
| `0004_agent_conversations` | `agent_conversations`, `agent_messages` (JSONB, append-only) |
| `0005_rag_chunks` | `rag_chunks` (passage text, embedding, generated `tsvector`, GIN + HNSW) |
| `0006_tracker_missions` | Bookmark `status`/`notes`/`applied_at`; `rss_items` `discovered_by`/`confidence`/`verified_at`/`flags`/`enriched_at`; tables `notifications`, `item_feedback`, `missions`, `mission_matches`, `agent_runs` (trace of agent and discovery runs) |

---

## 3. What is built

### Foundation and matching (phases 1–2)
- Bug fixes (bookmark id, indexed detail lookup), Alembic with an idempotent baseline, pytest against real Postgres, editable profile chips.
- Semantic matching: `all-MiniLM-L6-v2` via `fastembed` (ONNX, no PyTorch); hybrid score 0.7 × cosine + 0.3 × keyword, keyword fallback when the model isn't loaded.

### MCP server and Compass Assistant (phases 3–4)
- `mcp-server/`: **30 tools, 2 resources, 3 prompts** (`skill_gap`, `cover_letter`, `weekly_plan`). Covers search, postings, deadlines, bookmarks, profile, RAG, applications, missions, insights, coach, standup and pay insights.
- `/assistant`: streaming SSE chat with tool chips, history and Stop. Runs the same MCP server in-process with the user's JWT, so tools and permissions are shared.
- Only the tools relevant to each request are sent to the model (`tool_select.py`), which keeps Groq's free-tier token budget in check.
- Guardrails: 8 tool rounds plus a final answer, errors returned to the model as results, posting text treated as untrusted.

### RAG over posting text (phase 5)
- Sentence-packed passages, hybrid full-text + vector retrieval merged with Reciprocal Rank Fusion.
- "Ask this posting" with cited answers or "Not stated in this posting"; cross-posting search, comparison, resume-to-posting match.
- `backend/eval/rag_eval.py` evaluation harness (not yet run on a labeled set, see §4).

### Discovery (phase 6)
- **ATS boards:** Greenhouse, Lever, Ashby and others for a company watchlist (`ats_watchlist.json`, currently 3 entries).
- **HN "Who's Hiring":** Algolia API plus LLM extraction of postings from comments.
- **Devpost** hackathons, **scholarly** sources (arXiv/Semantic Scholar) for research, **open-source programs** (GSoC, Outreachy, LFX, MLH).
- **Web Search Agent** (Tavily/Brave), **Source Scout** proposes new feeds that an admin approves or rejects.

### Pipeline, Missions and product features (phase 7)
- Discovery pipeline with schema-validated extraction, verification (link alive, deadline, scam, duplicate), enrichment and ranking.
- **Missions:** saved natural-language searches that run on a schedule and report only new matches.
- **Notifications:** stored in Postgres and streamed over SSE (`/api/notifications/stream`, short polling with keep-alives) to a bell in the navbar.
- **Application tracker:** Kanban `/applications` (saved → applied → interview → offer/rejected, with notes), `/deadlines`, `.ics` export.
- **Insights:** explainable ranking, scam/eligibility/remote/stipend signals, skill-demand trends, company briefs, project suggestions, feedback (thumbs up/down, not interested).
- **Coach:** outreach drafts, research-lab scout, mock interview questions and feedback, personal memory search.
- **Ingestion QA v2:** versioned, explainable rules hide error pages, podcasts, listicles, news, dev logs and recaps from every discovery surface (33 of 2,375 dev-DB postings), reversible via `qa:<reason>` flags.
- **Career standup:** `GET /api/standup`, MCP tool `career_standup`, "Your week" card; up to 3 ranked actions computed from the user's own data.
- **Pay insights:** corrected stipend extraction (yearly vs monthly, currencies, prizes excluded); `GET /api/insights/stipends` with medians, interquartile range, sample sizes and coverage.
- **G8:** workers run in a separate `worker` container under Docker Compose (`RUN_WORKERS_IN_API=false`).

### External MCP clients (phase 8) 🟢
The assistant can host external MCP servers from `backend/app/services/agent/mcp_clients.json`:
Google Calendar, Gmail, GitHub, Notion, Fetch, Brave Search, Playwright. All ship disabled.

---

## 4. Verification

### Real-LLM validation (2026-11-09, Groq `openai/gpt-oss-120b`, dev DB: 2,174 postings, 8,227 passages)

| Check | Result |
|---|---|
| Ask this posting (5 questions, 3 postings) | Accurate and grounded, correct "Not stated" |
| Assistant tool loop (search, get, find_in_posting) | Works; answered with 2 real ML internships |
| Mission query parsing, interview questions and feedback, outreach draft | Work |
| Discovery live run (Lever, Greenhouse, Ashby, HN, Devpost) | 201 postings upserted; clean HN extraction |

Bugs found and fixed during that run: a retired default Groq model, the 【n】 citation format, no retry on HTTP 429, and Groq's 8k tokens/minute limit (now bounded by smaller `max_tokens`, `reasoning_effort=low`, 5,000-char tool results, per-request tool selection and retries that honor `retry-after`).

### Still unverified against the real service

| Item | What's needed |
|---|---|
| Anthropic provider (`AGENT_PROVIDER=anthropic`) | One assistant and one "Ask this posting" run with `ANTHROPIC_API_KEY` |
| Web Search Agent | `TAVILY_API_KEY` or `BRAVE_API_KEY` and one discovery run |
| External MCP servers | Real package names for Gmail and Google Calendar (still `<...-package>` placeholders), then enable and try each |
| Gmail inbox agent | Gmail MCP plus OAuth |
| RAG quality numbers | Run `backend/eval/rag_eval.py` on 10–20 labeled real postings |
| Full Docker stack | `docker compose --profile app up`: API + worker container + SSE bell + cookie sessions together |
| Frontend | No automated tests; only manual browser checks so far |

---

## 5. Known issues (re-verified 2026-11-10)

| Issue | Where | Status |
|---|---|---|
| A failed first message leaves an empty chat in the sidebar | `backend/app/routers/agent.py`: the conversation is created before the agent runs and is not removed on failure | Open (low) |
| Lint error: synchronous `setState` inside an effect | `frontend/src/lib/useProfile.ts:90` | Open |
| Lint warning: unused `router` | `frontend/src/app/profile/page.tsx:17` | Open |
| ATS watchlist has only 3 companies | `services/discovery/ats_watchlist.json` | Grow it |
| Free-tier Groq makes an agent turn slow (about 2 min for 5 tool rounds) | provider limits | Paid tier or Claude |
| Most stipend data is US-remote, so INR conversions look large | pay insights | Documented; USD/yr shown beside each figure |
| Untracked root files (`package.json`, `package-lock.json`, `dell_resume.pdf`, `typeface_resume.pdf`) | repo root | Remove or `.gitignore` |
| Demo account `demo@unicompass.dev` in the dev DB | dev DB | Delete when done |

Fixed since the last update: RemoteOK 410 sources removed, `google.generativeai` migrated to `google.genai`, HTML entities in feed cards cleaned (`frontend/src/lib/text.ts`), "from 0 sources" header fixed, workers moved out of the API process (G8), JWT moved to an httpOnly cookie (G9).

---

## 6. Future plans

### 6.1 Next up: close out and ship (days)
1. Fix the empty-chat bug and the two lint problems.
2. Run the full Docker stack end to end.
3. One real Anthropic run, then `rag_eval.py` on a labeled set; publish faithfulness and context-precision numbers.
4. Frontend smoke tests with Playwright: login, feed, assistant, applications board, missions.
5. Add CI (GitHub Actions): backend pytest with a pgvector service container, MCP tests, `tsc` and `eslint`.
6. Merge `agentic-roadmap` into `main` and push.

### 6.2 Quality and operations (weeks)
- **Observability:** export `agent_runs` traces to Langfuse or OpenTelemetry; dashboard for token cost, latency and tool errors per run.
- **Push notifications:** replace SSE polling with Redis pub/sub (or Postgres `LISTEN/NOTIFY`) so alerts arrive instantly without a query per open tab.
- **Cost guardrails:** per-user and per-mission token budgets enforced in the agent loop, not just per call.
- **Grow sources:** expand the ATS watchlist to 50+ companies; add Unstop and Kaggle adapters.
- **Retrieval quality:** cross-encoder reranking on top of RRF; full-page fetching for every posting so RAG isn't limited to feed summaries.
- **Deployment:** host the stack (Render or similar) with managed Postgres + pgvector and Redis.

### 6.3 New agentic features (larger)

| Feature | What the user gets | Depends on |
|---|---|---|
| Agentic RAG | Query rewriting, multi-hop retrieval (company → role → interview), a self-check that verifies citations | RAG eval baseline |
| Interview-prep RAG | Answers from indexed interview-experience posts; feeds the mock-interview coach | New community sources |
| Application pipeline | Researcher → Tailor → Writer → Reviewer agents draft a tailored resume and cover letter; the user approves before anything is sent | Agentic RAG |
| Community watchers | Reddit, Discord and Telegram hiring channels with LLM extraction and scam filtering | Ingestion QA rules |
| Hidden job market scout | Funding news (TechCrunch, YourStory, Inc42) → startups likely to hire soon | Web search key |
| GitHub enrichment | Skills from the user's repositories; "good first issue" discovery | GitHub MCP client |
| Calendar and Gmail actions | Deadlines and interviews added to the calendar; job-alert emails parsed (the allowed route for LinkedIn alerts) | External MCP clients verified |
| Browser agent | Playwright for JS-heavy sites without feeds, respecting robots.txt | Playwright MCP client |

### 6.4 Stretch ideas
- Skill ↔ Role ↔ Company ↔ Course graph (GraphRAG) for "what should I learn next?".
- Peer features: share postings, form hackathon teams, campus-specific feeds.
- Autofill browser extension that fills applications from the profile; the user submits.
- Voice mode for the mock-interview coach.

**Principles that stay fixed:** agents draft, the user approves; fetched pages are data, never instructions; no LinkedIn scraping or cookie-based LinkedIn MCP servers (use job-alert emails, PDF profile import and search-API links instead).

---

## 7. Configuration and running

`backend/.env` (or `.env.local`):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/unicompass
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<32+ chars>              # or leave unset in dev: generated into backend/.secret_key

GROQ_API_KEY=...                    # resume parsing, assistant, RAG answers, extraction
AGENT_PROVIDER=groq                 # or anthropic
ANTHROPIC_API_KEY=...               # when AGENT_PROVIDER=anthropic (claude-opus-5-5)
# GROQ_MODEL=openai/gpt-oss-120b    # default
# GROQ_MAX_OUTPUT_TOKENS=1500
# AGENT_TOOL_RESULT_CHARS=5000
GEMINI_API_KEY=...                  # optional resume-parser fallback (PROFILE_AI_PROVIDER)

EMBEDDINGS_ENABLED=true
RUN_WORKERS_IN_API=true             # false when the worker container runs

# Optional sources
ADZUNA_APP_ID= / ADZUNA_APP_KEY= / JOOBLE_API_KEY=
TAVILY_API_KEY= / BRAVE_API_KEY=    # Web Search Agent
```

MCP server: `UNICOMPASS_API_URL`, `UNICOMPASS_EMAIL`, `UNICOMPASS_PASSWORD` (or `UNICOMPASS_TOKEN`).

```bash
# Infrastructure only, run API and frontend locally
docker compose up -d postgres redis
cd backend && python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/uvicorn app.main:app --port 8000      # migrates on startup
cd ../frontend && npm install && npx next dev -p 3001

# Or the whole backend in containers (API + separate worker)
docker compose --profile app up -d

# Tests
docker run -d --rm --name unicompass-test-pg -p 5433:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=unicompass_test pgvector/pgvector:pg16
cd backend && venv/bin/pytest
cd ../mcp-server && .venv/bin/pytest
cd ../frontend && npx tsc --noEmit && npx eslint
```

**Notes for this dev machine:**
- Docker port forwarding to `localhost` is broken: point `DATABASE_URL`, `REDIS_URL` and `TEST_DATABASE_URL` at the container IPs (`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <name>`).
- ROS's `PYTHONPATH` breaks pytest and imports: prefix commands with `env -u PYTHONPATH`.
