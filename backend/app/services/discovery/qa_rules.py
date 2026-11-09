"""Ingestion QA rules: decide whether a stored posting is really an opportunity.

The RSS content filter is a first, per-category regex pass. These rules are the second pass that
runs over what is already stored and catches what slipped through:

  - feed/bridge error items ("Bridge returned error 0!")
  - podcast episodes, newsletters and webinars filed as courses
  - listicles and opinion/news articles
  - first-person dev logs and tutorials posted under hackathons, research or courses
  - hackathon recaps and winner announcements (the event is over)

Rules are category-aware so real postings are not caught by look-alike words: a job at
"Essence Journey" or "Hiring: Building the Agent Context Layer" is untouched, because the
dev-log rules only apply to hackathon, research and course posts.

Every rejection carries a reason, stored as a `qa:<reason>` flag next to `not-opportunity`, so a
wrong call can be found, explained and reversed. Bump QA_VERSION when the rules change and stored
rows are re-checked on the next run.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

QA_VERSION = 2
QA_FLAG = f"qa-v{QA_VERSION}"
REJECT_FLAG = "not-opportunity"
REASON_PREFIX = "qa:"

_I = re.IGNORECASE

# Rules for every category -------------------------------------------------------------------------
_ERROR_TITLE = re.compile(
    r"^\s*(bridge returned error|error\s*\d{3}|\d{3}\s+(not found|forbidden|error)|not found|access denied|"
    r"just a moment|attention required|page not found|service unavailable)", _I)
_NON_POSTING_MEDIA = re.compile(
    r"\bpodcast\b|\bepisode\s*#?\d+|\bep\.?\s*#?\d+\b|\bnewsletter\b|\bwebinar (replay|recording)\b|"
    r"\bweekly (digest|roundup|round-up)\b|\bthis week in\b", _I)
_LISTICLE = re.compile(
    r"^\s*(the\s+)?(top\s+)?\d+\+?\s+(best|ways|tips|reasons|free|top|things|tools|mistakes|resources|courses)\b|"
    r"^\s*(the\s+)?(best|ultimate|complete)\s+(guide|list)\b|\bbest .{0,40}\bin 20\d\d\b", _I)
_NEWS = re.compile(r"^\s*(opinion|report|analysis|news|breaking|exclusive|interview)\s*[:|\-–]|"
                   r"\b(raises|secures|closes)\s+\$?\d", _I)

# Rules for hackathon / research / course posts only (blogs and write-ups live here) ----------------
_DEVLOG = re.compile(
    r"^\s*(how\s+(i|we)\b|i\s+(built|made|created|developed|won|shipped)\b|we\s+(built|made|created|won)\b|"
    r"my\s+(journey|experience|story|first|hackathon)\b|what\s+(i|we)\s+learned\b|lessons?\s+(learned|from)\b)|"
    r"\b(day|week|part)\s+\d+\s+(of|:)\s|\b(dev ?log|post-?mortem|behind the scenes)\b|"
    r"\bhackathon\s+(snapshot|diary|recap|retrospective|journal)\b", _I)
# Project write-ups titled "Building X ..." are common under hackathons, but "Building REST APIs" is a real course.
_BUILDING_POST = re.compile(r"^\s*(building|breaking things)\b", _I)
_TUTORIAL = re.compile(r"\btutorial\b|\bstep[- ]by[- ]step\b|\bhow to (build|create|make|use|set up)\b", _I)
_OVER = re.compile(
    r"\b(winners?|results?|finalists?)\s+(announced|revealed|are in|list)\b|\bannouncing\s+(the\s+)?winners?\b|"
    r"\brecap\b|\bwrap[- ]?up\b|\bthank you (for|to all)\b|\bhighlights from\b", _I)

_SOFT_CATEGORIES = {"hackathon", "research", "course"}


@dataclass(frozen=True)
class QAVerdict:
    reject: bool
    reason: str = ""

    @property
    def flags(self) -> list[str]:
        return [REJECT_FLAG, f"{REASON_PREFIX}{self.reason}"] if self.reject else []


OK = QAVerdict(False)


def classify(title: str, summary: str, category: str) -> QAVerdict:
    """Return a verdict for one posting. `summary` is only used for the over/recap signals."""
    title = (title or "").strip()
    summary = summary or ""
    if not title:
        return QAVerdict(True, "empty-title")
    if _ERROR_TITLE.search(title):
        return QAVerdict(True, "error-page")
    if _NON_POSTING_MEDIA.search(title):
        return QAVerdict(True, "media-not-posting")
    if _LISTICLE.search(title):
        return QAVerdict(True, "listicle")
    if _NEWS.search(title) and category != "job":
        return QAVerdict(True, "news-article")

    if category in _SOFT_CATEGORIES:
        if _OVER.search(title):
            return QAVerdict(True, "event-over")
        if _DEVLOG.search(title) or (category == "hackathon" and _BUILDING_POST.search(title)):
            return QAVerdict(True, "dev-log")
        if _TUTORIAL.search(title) and category != "course":  # tutorials are what courses are
            return QAVerdict(True, "tutorial")
        if category == "hackathon" and _OVER.search(summary[:300]) and not re.search(r"\b(register|apply|deadline|open)\b", summary[:600], _I):
            return QAVerdict(True, "event-over")
    return OK
