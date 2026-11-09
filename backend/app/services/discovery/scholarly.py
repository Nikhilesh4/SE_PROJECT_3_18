"""Research Lab Scout: papers → authors → labs → a drafted cold email.

arXiv (Atom API) and Semantic Scholar (Graph API) find recent papers on a
topic. Frequent authors become *suggested people to contact*, each with their
affiliation, homepage and papers. `draft_cold_email` writes a short, specific
first message (via the LLM when configured, else a plain template) for the
student to review and send themselves. Nothing is ever sent automatically.
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import asdict, dataclass, field

import httpx

from app.config import settings

logger = logging.getLogger("discovery.scholarly")
ARXIV = "https://export.arxiv.org/api/query"
S2 = "https://api.semanticscholar.org/graph/v1/paper/search"
_NS = {"a": "http://www.w3.org/2005/Atom"}


@dataclass
class Paper:
    title: str
    url: str
    year: int | None
    authors: list[str]
    abstract: str = ""
    source: str = "arxiv"


@dataclass
class Person:
    name: str
    papers: list[str] = field(default_factory=list)
    affiliations: list[str] = field(default_factory=list)
    homepage: str | None = None
    s2_author_id: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def parse_arxiv(xml_text: str) -> list[Paper]:
    root = ET.fromstring(xml_text)
    papers = []
    for e in root.findall("a:entry", _NS):
        published = (e.findtext("a:published", "", _NS) or "")[:4]
        papers.append(Paper(
            title=" ".join((e.findtext("a:title", "", _NS) or "").split()),
            url=(e.findtext("a:id", "", _NS) or "").strip(),
            year=int(published) if published.isdigit() else None,
            authors=[a.findtext("a:name", "", _NS) for a in e.findall("a:author", _NS)],
            abstract=" ".join((e.findtext("a:summary", "", _NS) or "").split())[:600],
            source="arxiv",
        ))
    return papers


def parse_s2(payload: dict) -> tuple[list[Paper], dict[str, Person]]:
    papers, people = [], {}
    for p in payload.get("data", []):
        names = []
        for a in p.get("authors", []):
            names.append(a.get("name", ""))
            person = people.setdefault(a.get("name", ""), Person(a.get("name", ""), s2_author_id=a.get("authorId")))
            person.affiliations = sorted(set(person.affiliations) | set(a.get("affiliations") or []))
            person.homepage = person.homepage or a.get("homepage")
            person.papers.append(p.get("title", ""))
        papers.append(Paper(p.get("title", ""), (p.get("openAccessPdf") or {}).get("url") or f"https://www.semanticscholar.org/paper/{p.get('paperId')}",
                            p.get("year"), names, (p.get("abstract") or "")[:600], "semantic_scholar"))
    return papers, people


def scout(topic: str, *, limit: int = 10, client: httpx.Client | None = None) -> dict:
    """Papers + suggested contacts for a topic. Each source fails independently."""
    own = client is None
    client = client or httpx.Client(timeout=25, follow_redirects=True, headers={"User-Agent": "UniCompass/1.0"})
    papers: list[Paper] = []
    people: dict[str, Person] = {}
    errors: list[str] = []
    try:
        try:
            r = client.get(ARXIV, params={"search_query": f"all:{topic}", "sortBy": "submittedDate", "sortOrder": "descending", "max_results": limit})
            r.raise_for_status()
            papers += parse_arxiv(r.text)
        except Exception as exc:
            errors.append(f"arxiv: {exc}")
        try:
            headers = {"x-api-key": settings.SEMANTIC_SCHOLAR_API_KEY} if settings.SEMANTIC_SCHOLAR_API_KEY else {}
            r = client.get(S2, params={"query": topic, "limit": limit, "fields": "title,year,abstract,openAccessPdf,authors.name,authors.affiliations,authors.homepage,authors.authorId"}, headers=headers)
            r.raise_for_status()
            s2_papers, people = parse_s2(r.json())
            papers += s2_papers
        except Exception as exc:
            errors.append(f"semantic_scholar: {exc}")
    finally:
        if own:
            client.close()

    # Rank authors by how many of the found papers they appear on (senior/last authors usually run the lab).
    counts: dict[str, list[str]] = defaultdict(list)
    for p in papers:
        for i, name in enumerate(p.authors):
            if name:
                counts[name].append(p.title)
    contacts = []
    for name, titles in sorted(counts.items(), key=lambda kv: -len(kv[1]))[:5]:
        person = people.get(name) or Person(name)
        person.papers = sorted(set(titles))[:3]
        contacts.append(person.as_dict())
    return {"topic": topic, "papers": [asdict(p) for p in papers[: limit * 2]], "contacts": contacts, "errors": errors}


def template_cold_email(*, student_name: str, topic: str, person: str, paper: str, skills: list[str]) -> dict:
    first = person.split()[-1] if person else "Professor"
    skill_line = f" I have worked with {', '.join(skills[:4])}." if skills else ""
    return {
        "subject": f"Research internship enquiry: {topic}",
        "body": (
            f"Dear Professor {first},\n\nI am {student_name}, a student interested in {topic}. I read your paper “{paper}” and was particularly "
            f"interested in its approach.{skill_line} I would be grateful for the chance to contribute to your group as a research intern, "
            f"and I have attached my resume. Would you have a few minutes to discuss whether there is a fit?\n\nThank you for your time,\n{student_name}"
        ),
        "generated_by": "template",
    }
