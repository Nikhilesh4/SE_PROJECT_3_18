# UniCompass: Agentic Roadmap and Implementation Status

> Last updated: 2026-11-09 · Branch: `agentic-roadmap` (not merged into `main`, not pushed)

This document tracks the plan to finish UniCompass and turn it into an agentic, MCP-connected
career platform. It covers what is built, what is in progress, and everything still to do.

**Status legend:** ✅ Done and committed · 🟢 Committed, automated tests pass, never run against a real LLM or search key · ⬜ Not started

> **Update 2026-11-09:** phases 6–8, G2 (SSE instead of WebSocket), G8 (separate worker container) and the cookie-session half of G9 are implemented and committed. Sections 5.1–5.5 below keep the original plan for reference. What is genuinely left is listed in §10.

---

## 1. Summary

UniCompass collects internships, jobs, hackathons, research positions, freelance work and courses
from RSS feeds and job APIs (Adzuna, Jooble), extracts a student's skills from their resume
(Groq/Gemini), and ranks the feed for them.

The roadmap had three goals:
1. **Finish what was started.** The requirements doc promised semantic matching (FR-4) and
   real-time notifications (FR-5), and there were bugs, no tests and no migrations.
2. **Make it more useful.** Deadline tracking, application tracking, skill-gap analysis and similar features.
3. **Make it agentic.** An AI assistant, an MCP server, RAG over postings, and autonomous discovery
   agents that look beyond RSS feeds.

### Progress at a glance

| Phase | What | Status | Commit |
|---|---|---|---|
| 1 | Foundation: bug fixes, Alembic, tests, editable profile | ✅ | `01c851b` |
| 2 | Semantic matching with pgvector embeddings (FR-4) | ✅ | `ef3ef2c` |
| 3 | UniCompass MCP server | ✅ | `e5ce779` |
| 4 | Compass Assistant (in-app agent) | ✅ | `c194e01` |
| 5 | RAG over posting text | ✅ | `8842d1d` |
| 6 | New discovery channels (ATS boards, HN, web search, scholarly, Devpost, programs, Source Scout) | 🟢 built, untested with a real LLM/search key | `2a83c6f` |
| 7 | Discovery pipeline, Missions, SSE notifications, digest, tracker, insights, coach | 🟢 built, untested with a real LLM key | `2a83c6f`, `c437b1b` |
| 8 | External MCP clients (all ship disabled; tested against a fake server only) | 🟢 | `2a83c6f` |

### Test status (current working tree)

| Suite | Result | How to run |
|---|---|---|
| Backend (`backend/tests`) | **155 passed** (needs the test Postgres, see §8) | see §8 |
| MCP server (`mcp-server/tests`) | **24 passed** | `cd mcp-server && .venv/bin/pytest` |
| Frontend type-check | **clean** (`tsc --noEmit`) | `cd frontend && npx tsc --noEmit` |

---

## 2. Architecture after phases 1–5

```
                       ┌─────────────── Next.js frontend (:3001) ───────────────┐
                       │ Feed · Detail (+ Ask this posting) · Bookmarks ·        │
                       │ Profile (editable chips) · Assistant (streaming chat)  │
                       └───────────────┬────────────────────────────────────────┘
                                       │ REST / SSE (JWT)
┌──────────────────────────────── FastAPI backend (:8000) ─────────────────────────────────┐
│ routers: auth · feeds · bookmarks · profile · agent · rag                               │
│                                                                                          │
│ Feed ranking (Strategy):  Hybrid (0.7·cosine + 0.3·keyword) │ Keyword │ Default          │
│ Compass Agent: loop.py ── LLMProvider (Groq | Claude) ── Toolbox ─┐                      │
│                                                                   │ in-process MCP       │
│        unicompass_mcp server ◄────────────────────────────────────┘ (ASGI, user's JWT)   │
│ RAG: chunking → rag_chunks (tsvector + vector) → hybrid retrieval (RRF) → cited answers  │
│                                                                                          │
│ Workers: rss_refresh · ingestion · embedding (vectors + RAG passages + backfill)          │
└───────────────┬──────────────────────────────┬───────────────────────────────────────────┘
                │                              │
     PostgreSQL 16 + pgvector             Redis 7 (cache-aside, TTL timestamps)

External assistants (Claude Desktop / Code / Cursor) ──stdio──► mcp-server/ ──HTTP──► backend
```

### Database migrations (Alembic, `backend/alembic/versions/`)

| Revision | Adds |
|---|---|
| `0001_baseline` | users, profiles, rss_items, bookmarks. Adopts databases created by the old `create_all` startup |
| `0002_drop_opportunities` | Drops the unused `opportunities` table, only if it is empty |
| `0003_rss_item_embeddings` | `rss_items.embedding vector(384)` + HNSW cosine index |
| `0004_agent_conversations` | `agent_conversations`, `agent_messages` (JSONB, append-only) |
| `0005_rag_chunks` 🟡 | `rag_chunks` (passage text, embedding, generated `tsvector`, GIN + HNSW indexes) |

Migrations run automatically when the API starts (`RUN_MIGRATIONS_ON_STARTUP=true`), or manually with
`alembic upgrade head`.

---

## 3. Completed work

### Phase 1: Foundation ✅ (`01c851b`)

| Item | Problem | Fix |
|---|---|---|
| G4 bookmark id | `/api/bookmarks` omitted `id`, so un-bookmarking from the bookmarks page broke | `id` included; regression test |
| G5 slow detail lookup | Backend loaded 2,000 items and scanned them; the frontend downloaded 500 items and searched in the browser | Indexed lookup by GUID/URL; route accepts URL ids containing `/`; new `/api/feeds/[id]` proxy; detail page uses it |
| G3 dead model | `Opportunity` model and table were never used | Removed; migration drops the table only if it is empty |
| G6 migrations | Schema changes ran as raw SQL at import time in `main.py` | Alembic with an idempotent baseline that adopts existing databases |
| G6 tests | No test suite existed (the README referenced one) | pytest suite against real Postgres, with Redis faked |
| G7 editable profile | Skills and interests were read-only after parsing | `PATCH /profile/me` (trim and de-duplicate) plus add/remove chips on the profile page |
| Fresh-install crash | SQLAlchemy 2.1 defaults to the `psycopg` v3 driver, but only `psycopg2` was installed | Pinned `sqlalchemy>=2.0,<2.1` |

### Phase 2: Semantic matching (FR-4) ✅ (`ef3ef2c`)

- **Model:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions), run with `fastembed` (ONNX) instead of PyTorch, which avoids about 2 GB of dependencies.
- **Embedding worker:** embeds new postings from every ingestion path and backfills existing ones. The upsert resets a posting's vector only when its title, summary or tags change.
- **`HybridRelevanceFetchStrategy`:** score = 0.7 × pgvector cosine similarity + 0.3 × keyword score. If the model isn't ready, it falls back to keyword ranking, and the two modes use separate cache keys.
- **Profiles** are embedded on upload and on edit.
- **Design decision:** query and posting texts are kept plain. Labels like "Skills and interests:" roughly halved the gap between relevant and irrelevant postings on a labeled sample.
- **Bug fixed:** the keyword sort crashed (`TypeError`) when two items tied on score and one had no date.
- **Verified live:** "machine learning" ranked a Computer Vision posting first, and "finance" ranked Fintech and Accounting postings first.

### Phase 3: UniCompass MCP server ✅ (`e5ce779`), extended in phase 5 🟡

`mcp-server/` is a separate package built on the `mcp` 2.x SDK (`MCPServer`, stdio). See [`mcp-server/README.md`](../mcp-server/README.md).

| Kind | Items |
|---|---|
| Tools (8 committed) | `search_opportunities`, `get_opportunity`, `upcoming_deadlines`, `list_bookmarks`, `bookmark_opportunity` (idempotent), `remove_bookmark`, `get_profile`, `update_profile` |
| Tools (4 added in phase 5 🟡) | `search_posting_text`, `find_in_posting`, `compare_opportunities`, `match_resume_to_opportunity` |
| Resources | `unicompass://profile`, `unicompass://bookmarks` |
| Prompts | `skill_gap`, `cover_letter`, `weekly_plan` |

- **Thin adapter:** it calls the backend's HTTP API as the user. It logs in with email/password and re-logs in when the 24 h token expires.
- **Backend addition:** `GET /api/feeds/items/{id}`, so every tool refers to a posting by the same integer id.
- **Verified live** over stdio against the running backend.

### Phase 4: Compass Assistant ✅ (`c194e01`)

- **Endpoint:** `POST /agent/chat` streams Server-Sent Events: text, tool calls, tool results, and a final `done`.
- **Pages:** `/assistant` has streaming answers, tool-activity chips, a chat history sidebar and a Stop button.
- **Providers:** Groq is the default (OpenAI-compatible streaming). Set `AGENT_PROVIDER=anthropic` for Claude (`claude-opus-5-5`, adaptive thinking, server-side refusal fallback `fallbacks="default"`).
- **Same tools as the MCP server:** the backend runs the MCP server in-process, and its HTTP calls go back into the app with the user's own JWT. One set of tool definitions, the same permissions.
- **Append-only history** in each provider's native format. Claude needs its thinking blocks sent back unchanged, so a chat stays on the provider that started it.
- **Guardrails:** a step limit of 8 tool rounds plus one granted final answer; bad JSON, crashes, and truncated or refused turns return to the model as error results; posting text is treated as untrusted.
- **Not verified with a real LLM:** this machine has no Groq or Anthropic key. Tests and the browser check used a scripted stand-in model, with everything else real.

---

## 4. In progress: Phase 5, RAG over posting text 🟡

**Status:** built in the working tree, all tests pass (69 backend, 20 MCP, frontend type-checks).
**Not committed yet.** Not exercised with a real LLM, because there is no API key.

### What is built

| Piece | Location | Notes |
|---|---|---|
| Chunking | `services/rag/chunking.py` | Sentence-packed passages of about 450 chars (max 700), one short sentence of overlap, plus a `Tags:` passage. HTML and entities cleaned |
| Storage | `models/rag_chunk.py`, migration `0005` | Passage text, embedding, generated `tsvector`; GIN + HNSW indexes; cascades when a posting is deleted |
| Indexing | `services/rag/indexer.py`, embedding worker | Re-chunked whenever a posting is (re)embedded; backfills postings indexed before the table existed |
| Retrieval | `services/rag/retrieval.py` | Hybrid: full-text (`websearch_to_tsquery`) + pgvector cosine, merged with Reciprocal Rank Fusion. Cross-posting search requires every term; meaning-only hits below 0.35 cosine are dropped; full-text-only fallback without the model |
| Grounded answers | `services/rag/answer.py` | Cites passages, or says "Not stated in this posting" |
| Resume ↔ posting | `services/rag/resume_match.py` | Ranks the resume lines most relevant to a posting |
| API | `routers/rag.py` | `GET /api/rag/search`, `GET /api/rag/items/{id}/passages`, `GET /api/rag/compare`, `GET /api/rag/items/{id}/resume-match` (auth), `POST /api/rag/items/{id}/ask` (auth, one LLM call) |
| Agent | `services/agent/loop.py` | System prompt routes posting questions to the RAG tools; tool chips show passage sources |
| MCP | `unicompass_mcp/server.py` | 4 new tools (see phase 3) |
| UI | `frontend/src/app/feed/[id]/AskPosting.tsx`, `lib/rag.ts` | "Ask this posting" box on the detail page |
| Tests | `backend/tests/test_rag.py` (19 tests) | Chunking, indexing and re-indexing, exact-term and meaning search, fallback, category filter, compare, resume match, ask with valid citations, "not stated", errors |

### To finish phase 5
- [ ] Review the diff and commit it on `agentic-roadmap`.
- [ ] Try "Ask this posting" with a real `GROQ_API_KEY` or `ANTHROPIC_API_KEY`.
- [ ] Check answer quality on 10–20 real postings (stipend, eligibility, location, remote).
- [ ] Known limit: postings only contain the feed summary (capped at 2,000 chars), so answers are only as complete as the feed. Fetching full posting pages belongs to phase 6/7 (Enricher).

### Planned RAG features not yet built ⬜

| Feature | What the user gets | Depends on |
|---|---|---|
| Interview-prep RAG | "What does Google ask SWE interns?" answered from indexed interview-experience posts | Phase 6 web fetch / Reddit sources |
| Company intel RAG | One-page company brief from about pages, news and funding | Phase 6 web fetch |
| Personal memory RAG | The assistant remembers notes, past applications and earlier chats | Application tracker (§5.2) |
| Agentic RAG | Query rewriting, multi-hop retrieval (company → role → interview), a self-check that verifies citations | The above |
| GraphRAG (stretch) | Skill ↔ Role ↔ Company ↔ Course graph to answer "what should I learn next?" | Structured skills extraction |
| RAG evaluation | A Ragas-style eval set (faithfulness, context precision) | A real LLM key |

---

## 5. Remaining work

### 5.1 Unfinished foundation items ⬜

| # | Item | Plan |
|---|---|---|
| G2 | **Real-time notifications (FR-5)** | `/ws/notifications` WebSocket plus a Redis subscriber. After ingestion, compare new posting embeddings with profile embeddings (both exist now) and publish `new_match` above a threshold. Add a bell/toast in `Navbar.tsx`. Merged into phase 7 |
| G8 | **Workers inside the API process** | The RSS workers make blocking calls on the event loop: `/health` responds slowly at startup and the server ignored SIGTERM during testing. Move workers to their own container (`arq` or Celery) in `docker-compose.yml` |
| G9 | **Security basics** ✅ (partly) | Done: `SECRET_KEY` placeholders and keys under 32 chars fail at startup, and an unset key is generated into `backend/.secret_key`; `slowapi` limits login, register (per IP) and resume upload (per user). Left: move the JWT from localStorage to an httpOnly cookie (needs the frontend to go through the Next.js proxy routes) |

### 5.2 Product features (not agentic) ⬜

1. **Deadline tracker:** "closing soon" filter, `.ics` export of bookmarks, reminders 3 days before a deadline.
2. **Application tracker (Kanban):** add `status` (saved → applied → interview → offer/rejected) and `notes` to bookmarks; new `/applications` board. Feeds personal-memory RAG.
3. **Skill-gap view:** "you match 7 of 10 skills; missing: Docker, K8s", with links to postings in the course category. The MCP `skill_gap` prompt already does this through an LLM.
4. **Explainable ranking:** show why a card ranks high (matched tags or title words, semantic score). The scores are already computed.
5. **Search and facets:** server-side full-text search (the `tsvector` work from RAG can be reused) plus location, remote, stipend and source filters.
6. **Feedback loop:** thumbs up/down, "not interested", and click tracking as per-user ranking weights.
7. **Peer and university features:** share postings, form hackathon teams, campus-specific feeds.
8. **More sources:** Unstop, Devpost, MLH, Kaggle, arXiv, Semantic Scholar (FR-1 promised Semantic Scholar). Each is a new `OpportunityAdapter`.

### 5.3 Phase 6: New discovery channels ⬜

Each channel is a new `OpportunityAdapter` registered in `AggregatorFacade`, so it reuses the existing
normalize → filter → dedupe → Postgres → embed → RAG pipeline. Add `discovered_by`, `confidence` and
`verified_at` columns to `rss_items`.

| Order | Channel | How | Why |
|---|---|---|---|
| 1 | **ATS career boards** | Public JSON job APIs of Greenhouse, Lever, Ashby, Workable, SmartRecruiters for a company watchlist | Structured, high quality, no scraping. Best value for the effort |
| 2 | **HN "Who's Hiring"** | HN Algolia API, then the LLM extracts postings from comments | Many startups and remote roles |
| 3 | **Web Search Agent** | LLM-generated queries from the profile, then Tavily/Brave/Exa, then fetch the page and extract structured fields | Broad coverage; cache results, cap per user |
| 4 | **Research Lab Scout** | arXiv + Semantic Scholar, then authors' lab pages, then suggested professors plus a drafted cold email | Research internships |
| 5 | Open-source programs | GSoC, Outreachy, LFX, MLH Fellowship; GitHub "good first issue" | Student-friendly |
| 6 | Hidden job market | Funding news (TechCrunch, YourStory, Inc42), then startups likely to be hiring | Outreach before postings exist |
| 7 | Reddit / Discord / Telegram | Watch hiring communities; LLM extraction | Needs scam filtering |
| 8 | Inbox agent | Gmail API/MCP parses placement-cell and job-alert emails (opt-in) | Also the allowed way to bring in LinkedIn |
| 9 | Browser agent | Playwright MCP for JS-heavy sites with no RSS | Respect robots.txt and ToS; rate-limit |

**LinkedIn:** its job APIs are for partners only, and scraping breaks its ToS (accounts get banned). The allowed routes:
- LinkedIn job-alert emails, read by the Inbox agent.
- Importing the "Save to PDF" profile, which the existing resume parser already handles.
- Sign In with LinkedIn (name, email and photo only).
- "Open on LinkedIn" buttons that link to a pre-filled job search.
- Search-API results that show only a link and snippet.

Avoid unofficial LinkedIn MCP servers that use the user's login cookie.

### 5.4 Phase 7: Multi-agent pipeline, Missions and notifications ⬜

```
Planner ──► Source workers (ATS | HN | Search | arXiv | Reddit | Browser)
             └─► Extractor (LLM → NormalizedRssItem, schema-validated)
                  └─► Verifier (link alive? deadline in future? scam? duplicate?)
                       └─► Enricher (full page fetch, stipend, location, eligibility, skills, embedding, RAG passages)
                            └─► Ranker (hybrid + feedback) ──► Notifier (WebSocket / digest)
```

- **Missions:** saved natural-language searches ("remote paid ML internships ≥ ₹20k, deadline after Dec") that run daily and report only new, verified matches.
- **Background agents:** Daily Digest, Deadline Watcher, Ingestion QA (cleans up items the regex filter gets wrong, such as blog posts in hackathons), Source Scout (proposes new feeds after admin approval).
- **Notifications (G2):** new matches pushed over WebSocket.
- **Guardrails:**
  - Token and cost budget per mission.
  - Domain allowlist.
  - Fetched pages treated as data, never as instructions.
  - An `agent_runs` trace table (optionally Langfuse).
  - Agents never apply or send anything on their own: they draft, and the user approves.

### 5.5 Phase 8: External MCP clients and extra ideas ⬜

The Compass Agent becomes an MCP host. It loads external servers from
`backend/app/services/agent/mcp_clients.json`, and the existing `Toolbox` is the integration point.

| MCP server | Use |
|---|---|
| Google Calendar | Add deadlines and interviews to the calendar |
| Gmail | Read job alerts, send digests, draft application emails |
| GitHub | Enrich skills from the user's repositories |
| Notion | Export the application tracker |
| Fetch / Firecrawl | Turn posting pages into Markdown (feeds the Enricher and RAG) |
| Brave / Exa / Tavily | Web search for the discovery agents |
| Playwright | Browser agent for JS-heavy sites |

**More job-search ideas:**
- **Scam detector:** an LLM plus heuristics (asks for fees, Telegram-only contact) shows a warning badge.
- **Eligibility checker:** reads year, CGPA, branch and location rules and greys out postings you aren't eligible for.
- **Reverse job search:** finds companies that fit you even without open postings.
- **Referral and outreach assistant:** drafts cold emails and LinkedIn notes for you to send.
- **Portfolio-project suggester:** suggests projects that close your skill gaps.
- **Skill-demand trends dashboard** built from ingested postings.
- **Stipend and salary insights** from Adzuna, Jooble and extracted data.
- **Autofill browser extension:** fills applications from your profile; you submit.
- **Mock-interview agent,** using interview-prep RAG; voice optional.
- **Weekly "career standup":** reviews your tracker and suggests this week's 3 actions.
- **Multi-agent application pipeline:** Researcher → Tailor → Writer → Reviewer, with human approval before anything is sent.

---

## 6. Known issues and loose ends

| Issue | Where | Severity |
|---|---|---|
| Phase 5 not committed | working tree | Commit after review |
| LLM features never run against a real API (no key on this machine) | agent, RAG ask | Needs one real test with `GROQ_API_KEY` or `ANTHROPIC_API_KEY` |
| A failed first message leaves an empty chat in the sidebar (retrying in it works) | `routers/agent.py` | Low |
| API startup is slow; workers block the event loop | G8 | Medium |
| Some summaries show raw HTML entities (`&#160;`) in the feed UI | frontend cards | Low (the MCP and RAG paths clean them) |
| Header says "from 0 sources"; the skills sidebar omits interests | feed page | Low |
| RemoteOK feeds return HTTP 410 | `feed_sources.py` | Remove the sources |
| The content filter lets some blog posts through as hackathons | `services/rss/filter.py` | Phase 7 Ingestion QA agent |
| `google.generativeai` is deprecated (FutureWarning) | resume parser | Migrate to `google.genai` |
| Untracked files not part of the project: root `package.json`/`package-lock.json` (an npm package named `claude`), `dell_resume.pdf`, `.postqode/` | repo root | Remove or `.gitignore` |
| Demo account `demo@unicompass.dev` and its test chats exist in the dev database | dev DB | Delete when no longer needed |

---

## 7. Configuration reference

`backend/.env` (or `.env.local`):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/unicompass
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=<32+ chars>          # or leave unset in dev: a key is generated into backend/.secret_key

# Resume parsing + Compass Assistant + Ask-this-posting
GROQ_API_KEY=...
AGENT_PROVIDER=groq                 # or anthropic
ANTHROPIC_API_KEY=...               # when AGENT_PROVIDER=anthropic (model claude-opus-5-5)
# AGENT_MODEL=                      # optional override
# GROQ_MODEL=openai/gpt-oss-120b    # default; llama-3.3-70b-versatile is no longer served by Groq
# GROQ_MAX_OUTPUT_TOKENS=1500       # Groq counts max_tokens against its 8k tokens/minute free-tier limit
# AGENT_TOOL_RESULT_CHARS=5000      # cap per tool result fed back to the model

# Semantic matching (defaults shown)
EMBEDDINGS_ENABLED=true
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# Optional job APIs
ADZUNA_APP_ID= / ADZUNA_APP_KEY= / JOOBLE_API_KEY=
```

MCP server environment: `UNICOMPASS_API_URL`, `UNICOMPASS_EMAIL`, `UNICOMPASS_PASSWORD` (or `UNICOMPASS_TOKEN`).

---

## 8. Running and verifying

```bash
docker compose up -d postgres redis
cd backend && python -m venv venv && venv/bin/pip install -r requirements.txt
venv/bin/uvicorn app.main:app --port 8000      # migrates on startup; first run downloads the ~90 MB model
cd ../frontend && npm install && npx next dev -p 3001   # RSS-Bridge holds :3000
```

Tests:

```bash
docker run -d --rm --name unicompass-test-pg -p 5433:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=unicompass_test pgvector/pgvector:pg16
cd backend && venv/bin/pytest
cd ../mcp-server && .venv/bin/pytest
```

**Machine-specific notes for this dev box:**
- **Docker port forwarding to `localhost` is broken.** Point `DATABASE_URL`, `REDIS_URL` and `TEST_DATABASE_URL` at the container IPs instead (`docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' <name>`).
- **ROS's `PYTHONPATH` breaks pytest and imports.** Prefix commands with `env -u PYTHONPATH`.

---

## 9. Recommended next steps

1. Commit phase 5, then run one real LLM test of the assistant and "Ask this posting".
2. G8 (move workers out of the API process). It's quick and improves every phase after it.
3. Phase 6: ATS boards and HN "Who's Hiring" first, then the Web Search Agent.
4. Phase 7: Missions, notifications (G2), Daily Digest and Deadline Watcher.
5. Application tracker and deadline features (§5.2), then personal-memory RAG.
6. Phase 8: external MCP clients (Calendar and Gmail first).

---

## 10. What is genuinely left (2026-11-09)

**Needs an API key (blocked on this dev machine)**
- Run the assistant, "Ask this posting", missions, coach, and discovery extraction against real Groq/Anthropic and Tavily/Brave keys.
- Run `backend/eval/rag_eval.py` on 10-20 real postings.
- Enable and try the external MCP servers (replace the `<...-package>` placeholders in `mcp_clients.json`).

**Not built**
- Reddit/Discord/Telegram watchers, funding-news "hidden market" scout, GitHub "good first issue" discovery.
- Langfuse/external tracing (an `agent_runs` table exists), weekly career-standup agent, aggregate stipend insights.
- Peer features (sharing, hackathon teams, campus feeds), autofill extension, GraphRAG, Researcher-Tailor-Writer-Reviewer pipeline.

**Loose ends from section 6 not re-verified:** RemoteOK 410 sources, HTML entities in feed cards, "from 0 sources" header, `google.generativeai` deprecation, empty chat after a failed first message, demo account in the dev DB.

### Real-LLM validation, 2026-11-09 (Groq, `openai/gpt-oss-120b`)

Run against the dev DB (2,174 postings, 8,227 RAG passages) with a real Groq key.

| Check | Result |
|---|---|
| Ask this posting (5 questions, 3 postings) | Accurate and grounded; correct "Not stated" |
| Assistant tool loop (search, get, find_in_posting) | Works; answered with 2 real ML internships |
| Mission query parsing, interview questions and feedback, outreach draft | Work |
| Discovery live run (ATS Lever/Greenhouse/Ashby, HN, Devpost) | 201 postings upserted; HN LLM extraction gave clean titles and companies |

Bugs found and fixed: the default Groq model had been retired (404 on every call); `gpt-oss` cites as 【n】 and the citation parser missed it; no retry on 429; Groq's 8k tokens/minute limit counts `max_tokens` and about 3.5k tokens of tool definitions per round (now bounded: smaller `max_tokens`, `reasoning_effort=low`, 5,000-char tool results, up to 6 retries honoring `retry-after`); the assistant said "found nothing" when only the deadline was missing (prompt fixed).

Still unverified: Anthropic provider, web search (no Tavily/Brave key), external MCP servers, the Gmail inbox agent. Free-tier Groq makes an agent turn slow (about 2 minutes for 5 tool rounds); a paid tier or Claude removes that.

### Ingestion QA v2 (2026-11-09)

`services/discovery/qa_rules.py` is a category-aware, versioned rule set (error pages, podcasts and newsletters, listicles, news, first-person dev logs, tutorials, recaps and winner announcements). Each rejection stores `not-opportunity` plus a `qa:<reason>` flag, so a wrong call can be found and reversed. Bumping `QA_VERSION` re-checks stored rows. QA runs first in every activity-worker cycle, so junk is hidden before it can trigger an alert. `RssItem.visible()` is applied to the feed, search, cross-posting RAG, missions, alerts, trends, company brief and public deadlines; direct lookups by id and a user's own saved items are not filtered.

On the dev DB it hides 33 of 2,375 postings (podcasts, listicles, dev logs, error pages, recaps). An earlier attempt to re-run the ingestion content filter on stored rows hid 344 real postings (stored summaries are truncated or enriched), so that fallback was removed and those flags reversed.

### Career standup (2026-11-09)

The weekly digest was already a career standup (a notification each ISO week). It is now also available on demand: `GET /api/standup`, the MCP/assistant tool `career_standup`, and a "Your week" card on `/applications`. Actions are ranked and capped at three: no resume, deadlines closing within 7 days, an upcoming interview, stale applications (14+ days), a skill missing from the profile that most tracked roles ask for, new matches, nothing applied yet, no active mission. Everything is computed from the user's own rows; `polish=true` only lets the LLM reword the summary.
