from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.db import SessionLocal
from app.repositories.profile_repository import ProfileRepository
from app.services.agent.providers import GroqProvider, LLMProvider, ProviderError, Turn
from app.services.matching.semantic import embed_pending_items
from app.services.rag.chunking import MAX_CHARS, chunk_posting
from app.services.rag.indexer import index_pending_items
from app.services.rag.resume_match import resume_units
from tests.conftest import _user_id, make_item

NOW = datetime.now(timezone.utc)


def _chunks(db) -> list[tuple[int, int, str]]:
    with db.connect() as conn:
        rows = conn.execute(
            text("SELECT rss_item_id, chunk_index, content FROM rag_chunks ORDER BY 1, 2")
        )
        return [tuple(r) for r in rows]


@pytest.fixture
def postings(seed_items):
    """Two postings, embedded and indexed through the worker's write path."""
    stored = seed_items(
        make_item(
            url="https://example.com/ml",
            title="Research Intern, Neural Networks",
            summary=(
                "Train deep learning models with PyTorch. "
                "The stipend is 30,000 INR per month. "
                "Open to second-year and third-year students in any engineering branch."
            ),
            tags=["pytorch"],
        ),
        make_item(
            url="https://example.com/frontend",
            title="React Frontend Intern",
            summary="Build UI with CSS and JavaScript. This role is fully remote. Unpaid.",
            published_at=NOW - timedelta(hours=2),
        ),
    )
    embed_pending_items()
    return stored


# ── Chunking ─────────────────────────────────────────────────────────────────

def test_chunking_packs_sentences_and_keeps_tags():
    summary = " ".join(f"Sentence number {i} talks about the role in some detail." for i in range(30))
    passages = chunk_posting("Title", ["python", "sql"], summary)
    assert len(passages) > 2
    assert all(len(p) <= MAX_CHARS for p in passages)
    assert passages[-1] == "Tags: python, sql"
    # one sentence of overlap keeps context across passage boundaries
    assert passages[0].split(". ")[-1].rstrip(".") in passages[1]


def test_chunking_cleans_html_and_always_returns_a_passage():
    assert chunk_posting("Only a title", [], "") == ["Only a title"]
    assert chunk_posting("T", [], "<p>Paid&#160;role</p>") == ["Paid role"]


def test_resume_units_join_wrapped_lines_and_skip_headings():
    raw = (
        "EXPERIENCE\n"
        "• Built a PyTorch image classifier that reached 94% accuracy\n"
        "  on a 10k-image dataset.\n"
        "• Short\n"
        "PROJECTS\n"
        "- Wrote a React dashboard used by 200 students every week.\n"
    )
    assert resume_units(raw) == [
        "Built a PyTorch image classifier that reached 94% accuracy on a 10k-image dataset.",
        "Wrote a React dashboard used by 200 students every week.",
    ]


# ── Indexing ─────────────────────────────────────────────────────────────────

def test_embedding_worker_indexes_and_reindexes_changed_text(db, postings, seed_items):
    ml, frontend = postings
    assert {item_id for item_id, _, _ in _chunks(db)} == {ml.id, frontend.id}

    seed_items(make_item(url="https://example.com/frontend", title="React Frontend Intern",
                         summary="Now paid: 10,000 INR per month."))
    embed_pending_items()
    texts = [c for item_id, _, c in _chunks(db) if item_id == frontend.id]
    assert texts == ["Now paid: 10,000 INR per month."]


def test_backfill_indexes_items_embedded_before_rag(db, postings):
    with db.begin() as conn:
        conn.execute(text("DELETE FROM rag_chunks"))
    assert index_pending_items() == 2
    assert index_pending_items() == 0


def test_deleting_a_posting_deletes_its_passages(db, postings):
    with db.begin() as conn:
        conn.execute(text("DELETE FROM rss_items WHERE id = :id"), {"id": postings[0].id})
    assert {item_id for item_id, _, _ in _chunks(db)} == {postings[1].id}


# ── Retrieval ────────────────────────────────────────────────────────────────

def test_search_finds_exact_terms(client, postings):
    ml, _ = postings
    passages = client.get("/api/rag/search", params={"q": "stipend"}).json()["passages"]
    assert passages[0]["item_id"] == ml.id
    assert "stipend" in passages[0]["text"]
    assert passages[0]["match"] in {"keyword", "both"}
    assert passages[0]["url"] == "https://example.com/ml"


def test_search_finds_meaning_without_shared_words(client, postings):
    ml, _ = postings
    passages = client.get("/api/rag/search", params={"q": "AI"}).json()["passages"]
    assert passages and passages[0]["item_id"] == ml.id
    assert passages[0]["match"] == "semantic"


def test_search_falls_back_to_full_text_without_model(client, postings, no_embedder):
    passages = client.get("/api/rag/search", params={"q": "remote"}).json()["passages"]
    assert [p["item_id"] for p in passages] == [postings[1].id]
    assert client.get("/api/rag/search", params={"q": "AI"}).json()["passages"] == []


def test_search_respects_category(client, postings):
    passages = client.get("/api/rag/search", params={"q": "stipend", "category": "job"}).json()
    assert passages["passages"] == []


def test_item_passages_rank_the_answer_first_and_fill_with_context(client, postings):
    ml, _ = postings
    body = client.get(f"/api/rag/items/{ml.id}/passages",
                      params={"q": "which students are eligible?"}).json()
    assert {p["item_id"] for p in body["passages"]} == {ml.id}
    assert "second-year" in body["passages"][0]["text"]

    no_question = client.get(f"/api/rag/items/{ml.id}/passages").json()["passages"]
    assert no_question and all(p["match"] == "context" for p in no_question)
    assert client.get("/api/rag/items/999999/passages").status_code == 404


def test_compare_reports_each_aspect_or_none(client, postings):
    ml, frontend = postings
    body = client.get("/api/rag/compare", params={"ids": f"{ml.id},{frontend.id}",
                                                   "aspects": "pay,location"}).json()
    by_id = {p["id"]: p for p in body["postings"]}
    assert "30,000" in by_id[ml.id]["aspects"]["pay"]["text"]
    assert "remote" in by_id[frontend.id]["aspects"]["location"]["text"]
    assert body["aspects"] == ["pay", "location"]


def test_compare_validates_ids(client, postings):
    assert client.get("/api/rag/compare", params={"ids": "1"}).status_code == 422
    assert client.get("/api/rag/compare", params={"ids": "a,b"}).status_code == 422
    body = client.get("/api/rag/compare", params={"ids": f"{postings[0].id},999999"}).json()
    assert body["postings"][1] == {"id": 999999, "error": "Opportunity not found."}


# ── Resume match ─────────────────────────────────────────────────────────────

def test_resume_match_ranks_relevant_lines_first(client, auth_headers, postings):
    from app.schemas.profile import ProfileStructured

    db = SessionLocal()
    try:
        ProfileRepository().upsert_profile(
            db,
            _user_id(auth_headers),
            raw_text=(
                "• Designed CSS layouts for a college fest website and its sign-up pages.\n"
                "• Trained neural network models in PyTorch for plant disease detection.\n"
            ),
            parsed_profile=ProfileStructured(skills=["PyTorch", "Go"]),
        )
    finally:
        db.close()

    ml, _ = postings
    body = client.get(f"/api/rag/items/{ml.id}/resume-match", headers=auth_headers).json()
    assert body["ranked_by"] == "semantic"
    assert "PyTorch" in body["evidence"][0]["text"]
    assert body["matched_skills"] == ["PyTorch"]
    assert body["posting_tags_not_in_profile"] == []


def test_resume_match_needs_login_and_profile(client, auth_headers, postings):
    url = f"/api/rag/items/{postings[0].id}/resume-match"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=auth_headers).status_code == 404


# ── Grounded answers ─────────────────────────────────────────────────────────

class CannedProvider(LLMProvider):
    name = "canned"
    model = "canned-1"

    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.prompts: list[str] = []
        self.tools_seen: list = []

    async def stream_turn(self, *, system, history, tools, on_text):
        self.prompts.append(history[-1]["content"])
        self.tools_seen = tools
        if isinstance(self.reply, Exception):
            raise self.reply
        return Turn(assistant_message={"role": "assistant", "content": self.reply}, text=self.reply)

    user_message = GroqProvider.user_message
    tool_result_messages = GroqProvider.tool_result_messages
    visible = GroqProvider.visible


@pytest.fixture
def use_provider(monkeypatch):
    def install(reply):
        provider = CannedProvider(reply)
        monkeypatch.setattr("app.routers.rag.provider_for", lambda: provider)
        return provider

    return install


def test_ask_sends_ranked_passages_and_returns_valid_citations(client, auth_headers, postings, use_provider):
    ml, _ = postings
    provider = use_provider("Yes, it pays 30,000 INR per month [2]. See also [9].")
    resp = client.post(f"/api/rag/items/{ml.id}/ask", json={"question": "Is it paid?"},
                       headers=auth_headers)
    body = resp.json()
    assert resp.status_code == 200, body
    assert body["citations"] == [2]  # [9] doesn't exist
    assert body["not_found"] is False
    assert body["passages"][0]["match"] == "metadata"
    assert "stipend" in body["passages"][1]["text"]
    assert "QUESTION: Is it paid?" in provider.prompts[0]
    assert provider.tools_seen == []


def test_ask_flags_not_stated(client, auth_headers, postings, use_provider):
    use_provider("Not stated in this posting.")
    body = client.post(f"/api/rag/items/{postings[0].id}/ask", json={"question": "Visa?"},
                       headers=auth_headers).json()
    assert body["not_found"] is True and body["citations"] == []


def test_ask_errors(client, auth_headers, postings, use_provider):
    url = f"/api/rag/items/{postings[0].id}/ask"
    assert client.post(url, json={"question": "Paid?"}).status_code == 401
    use_provider(ProviderError("Groq is rate-limiting requests; try again shortly."))
    resp = client.post(url, json={"question": "Paid?"}, headers=auth_headers)
    assert resp.status_code == 503 and "rate-limiting" in resp.json()["detail"]
    use_provider("unused")
    assert client.post("/api/rag/items/999999/ask", json={"question": "Paid?"},
                       headers=auth_headers).status_code == 404


def test_cross_posting_search_needs_every_term_in_one_passage(client, postings, no_embedder):
    # "remote" is in one posting and "stipend" in the other: neither states both.
    assert client.get("/api/rag/search", params={"q": "remote stipend"}).json()["passages"] == []
    ml, frontend = postings
    # Within one posting any term counts, since the posting is already chosen.
    body = client.get(f"/api/rag/items/{frontend.id}/passages", params={"q": "remote stipend"}).json()
    assert body["passages"][0]["match"] == "keyword" and "remote" in body["passages"][0]["text"]


def test_normalize_answer_text_handles_model_citation_styles():
    from app.services.rag.answer import normalize_answer_text

    assert normalize_answer_text("Prize  $6,000【52】.") == "Prize  $6,000[52]."
    assert normalize_answer_text("Remote [1, 2] and paid【 3 】") == "Remote [1][2] and paid[3]"
    assert normalize_answer_text("Not stated in this posting. [2]") == "Not stated in this posting. [2]"
