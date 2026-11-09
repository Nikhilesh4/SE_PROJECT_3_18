"""Open-source and fellowship programs aimed at students.

These recur yearly and rarely have machine-readable feeds, so this is a small
curated catalogue (edit `PROGRAMS`). Each entry links to the program's own page;
`typical_window` is documentation, not a promised deadline, so no deadline is set.
"""

from __future__ import annotations

from app.schemas.rss_item import NormalizedRssItem
from app.services.adapters.base_adapter import OpportunityAdapter

PROGRAMS: list[dict] = [
    {"id": "gsoc", "title": "Google Summer of Code", "url": "https://summerofcode.withgoogle.com/", "category": "internship",
     "window": "applications open around March–April; coding runs May–September",
     "about": "Paid open-source internship with mentoring organisations such as Apache, Mozilla and the Linux Foundation. Open to students and beginners."},
    {"id": "outreachy", "title": "Outreachy Internships", "url": "https://www.outreachy.org/", "category": "internship",
     "window": "two rounds a year (May–August and December–March)",
     "about": "Paid remote open-source internships for people subject to systemic bias. Stipend of 7,000 USD."},
    {"id": "lfx", "title": "Linux Foundation LFX Mentorship", "url": "https://lfx.linuxfoundation.org/tools/mentorship/", "category": "internship",
     "window": "three terms a year: spring, summer, fall",
     "about": "Mentored, often paid, work on CNCF, Hyperledger, LF AI and other Linux Foundation projects."},
    {"id": "mlh-fellowship", "title": "MLH Fellowship", "url": "https://fellowship.mlh.io/", "category": "internship",
     "window": "multiple cohorts a year",
     "about": "12-week remote fellowship contributing to open-source projects, with a stipend."},
    {"id": "hacktoberfest", "title": "Hacktoberfest", "url": "https://hacktoberfest.com/", "category": "hackathon",
     "window": "every October", "about": "Month-long open-source contribution event; contributions earn swag and certificates."},
    {"id": "gsod", "title": "Google Season of Docs", "url": "https://developers.google.com/season-of-docs", "category": "freelance",
     "window": "annual; proposals in spring", "about": "Paid technical-writing projects with open-source organisations."},
]


class ProgramsAdapter(OpportunityAdapter):
    def fetch_opportunities(self, *, keywords: str = "", location: str = "", page: int = 1, limit: int = 20) -> list[NormalizedRssItem]:
        return [
            NormalizedRssItem(
                title=p["title"], url=p["url"], summary=f"{p['about']} Typical window: {p['window']}.",
                category=p["category"], source_name="Open-source programs", feed_url="curated",
                tags=["open-source", "students"], guid=f"program:{p['id']}", discovered_by="programs", confidence=0.9,
            )
            for p in PROGRAMS
        ]
