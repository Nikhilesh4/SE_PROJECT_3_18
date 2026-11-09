# UniCompass MCP Server

Lets an AI assistant (Claude Desktop, Claude Code, Cursor, or any MCP client)
use a student's UniCompass account: search opportunities ranked against their
profile, read postings, manage bookmarks, edit skills and track deadlines.

> *"Find computer-vision internships that match my profile, bookmark the best
> two, and run a skill-gap check on the top one."*

The server is a thin adapter over the UniCompass FastAPI backend. Ranking,
caching and authentication all stay in the backend; the server only calls its
HTTP API as the signed-in user.

## What it exposes

| Kind | Name | What it does |
|---|---|---|
| Tool | `search_opportunities(query?, category?, limit, offset, include_expired)` | Semantic search. Ranks against `query` if given, otherwise against the student's skills and interests |
| Tool | `get_opportunity(id)` | Full posting text, plus whether it's bookmarked |
| Tool | `upcoming_deadlines(days)` | Bookmarked items due within `days`, soonest first |
| Tool | `search_posting_text(query, category?, limit, include_expired)` | Passages from any posting that state a fact ("visa sponsorship"), for quoting. Hybrid full-text + semantic search |
| Tool | `find_in_posting(id, question?)` | One posting's passages, most relevant to the question first, for a cited answer |
| Tool | `compare_opportunities(ids, aspects?)` | 2–5 postings side by side: per aspect (pay, location, skills, eligibility, …) the passage that addresses it, or null |
| Tool | `match_resume_to_opportunity(id)` | The resume lines most relevant to a posting, matched skills, and posting tags the student lacks |
| Tool | `list_bookmarks(category?)` | Saved opportunities |
| Tool | `bookmark_opportunity(id)` | Save. Idempotent: a repeat call never un-saves |
| Tool | `remove_bookmark(id)` | Unsave (marked destructive, so clients ask first) |
| Tool | `get_profile()` | Skills, interests, education and experience parsed from the resume |
| Tool | `update_profile(add_skills?, remove_skills?, add_interests?, remove_interests?)` | Edit lists. Removal ignores case. Changes re-rank the feed immediately |
| Resource | `unicompass://profile`, `unicompass://bookmarks` | The same data as JSON, for attaching as context |
| Prompt | `skill_gap(id)` | Requirement-by-requirement comparison with the profile, plus a plan to close gaps |
| Prompt | `cover_letter(id, tone?)` | Tailored draft using only facts from the profile, led by the most relevant resume lines |
| Prompt | `weekly_plan()` | Deadlines plus new matches turned into a day-by-day plan |

Every opportunity carries an integer `id`, the same id the bookmark endpoints use.
Summaries are converted to plain text (HTML tags and entities removed).

## Setup

Requires Python 3.11+ and a running UniCompass backend (see the root README).

```bash
cd mcp-server
python -m venv .venv
.venv/bin/pip install -e .          # Windows: .venv\Scripts\pip install -e .
```

Configuration is read from environment variables:

| Variable | Default | Meaning |
|---|---|---|
| `UNICOMPASS_API_URL` | `http://localhost:8000` | FastAPI backend (not the Next.js frontend) |
| `UNICOMPASS_EMAIL` / `UNICOMPASS_PASSWORD` | none | The account to act as. The server logs in on first use and again when the 24 h token expires |
| `UNICOMPASS_TOKEN` | none | Alternative to email/password: a JWT from `POST /auth/login`. It stops working after 24 h |

### Claude Code

```bash
claude mcp add unicompass \
  -e UNICOMPASS_API_URL=http://localhost:8000 \
  -e UNICOMPASS_EMAIL=you@example.com \
  -e UNICOMPASS_PASSWORD='your-password' \
  -- /absolute/path/to/mcp-server/.venv/bin/unicompass-mcp
```

### Claude Desktop / Cursor

Add this to `claude_desktop_config.json` (Cursor: `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "unicompass": {
      "command": "/absolute/path/to/mcp-server/.venv/bin/unicompass-mcp",
      "env": {
        "UNICOMPASS_API_URL": "http://localhost:8000",
        "UNICOMPASS_EMAIL": "you@example.com",
        "UNICOMPASS_PASSWORD": "your-password"
      }
    }
  }
}
```

The password is stored in plain text in that config file. Use a UniCompass account
made for this purpose, or a short-lived `UNICOMPASS_TOKEN` instead.

### Try it without an assistant

```bash
npx @modelcontextprotocol/inspector .venv/bin/unicompass-mcp
```

## Development

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

The tests run the real MCP protocol through an in-process `mcp.Client` against
a fake backend (`httpx.MockTransport`). They need no database or model and cover
ranking modes, idempotent bookmarking, deadline filtering, token refresh, and the
error messages the model sees.

Built on the `mcp` 2.x SDK (`MCPServer`). This is the renamed successor of v1's `FastMCP`.
