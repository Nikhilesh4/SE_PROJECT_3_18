"""ATS check: how well a resume reads to an applicant-tracking system, and what to change
to match one posting.

Everything here is deterministic and works on the resume's own text, because that is what an
ATS parses: keywords it can find, standard section headings, contact details, plain layout.
The assistant turns the findings into advice; this module never invents resume content, and
every suggestion about a missing keyword is conditional on the student truly having the skill.
"""

from __future__ import annotations

import re

from app.models.profile import Profile
from app.models.rss_item import RssItem
from app.services.insights import explain, signals

SECTIONS = {
    "experience": r"experience|employment|internships?|work history",
    "education": r"education|academics?|qualifications?",
    "skills": r"skills|technologies|technical skills|tech stack",
    "projects": r"projects?",
}
_ACTION_VERBS = {
    "built", "developed", "designed", "implemented", "created", "led", "managed", "improved", "reduced",
    "increased", "optimized", "optimised", "automated", "deployed", "launched", "analyzed", "analysed",
    "engineered", "integrated", "migrated", "wrote", "trained", "architected", "delivered", "collaborated",
    "researched", "organized", "organised", "mentored", "refactored", "tested", "maintained", "drove",
}
_BULLET_RE = re.compile(r"^\s*[•●▪◦‣*\-–]\s*(.+)")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{8,}\d)(?!\d)")
_NUMBER_RE = re.compile(r"\d")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z+#.]*")


def _mentions(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9+#]){re.escape(term.lower())}(?![a-z0-9+#])", text.lower()) is not None


def _check(name: str, ok: bool, detail: str, fix: str | None = None, weight: int = 1) -> dict:
    return {"name": name, "ok": ok, "detail": detail, "fix": None if ok else fix, "weight": weight}


def _format_checks(text: str) -> list[dict]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    words = _WORD_RE.findall(text)
    bullets = [m.group(1) for ln in lines if (m := _BULLET_RE.match(ln))]
    checks: list[dict] = []

    checks.append(_check(
        "Length", 150 <= len(words) <= 1000, f"{len(words)} words",
        "Aim for roughly 300–700 words; one page for a student resume.", 2,
    ))
    for key, pattern in SECTIONS.items():
        found = any(re.fullmatch(rf"\W*(?:{pattern})\W*", ln.strip(), re.IGNORECASE) for ln in lines)
        checks.append(_check(
            f"'{key.title()}' section heading", found,
            "found" if found else "not found as a standalone heading",
            f"Add a plain heading called \"{key.title()}\" — ATS parsers file content under standard headings.",
            2 if key in ("experience", "education", "skills") else 1,
        ))
    head = "\n".join(lines[:12])
    checks.append(_check("Email address", bool(_EMAIL_RE.search(head or text)), "", "Put your email in the header as plain text.", 2))
    checks.append(_check("Phone number", bool(_PHONE_RE.search(head or text)), "", "Add a phone number in the header.", 1))
    checks.append(_check(
        "LinkedIn / GitHub link", bool(re.search(r"linkedin\.com|github\.com", text, re.IGNORECASE)), "",
        "Add your LinkedIn and GitHub URLs as visible text (not only hyperlinked words).", 1,
    ))
    checks.append(_check(
        "Bullet points", len(bullets) >= 5, f"{len(bullets)} bullets found",
        "Describe experience and projects as short bullets (3–5 per role).", 1,
    ))
    if bullets:
        verbs = sum(1 for b in bullets if b.split()[0].lower().strip(",.") in _ACTION_VERBS)
        checks.append(_check(
            "Bullets start with action verbs", verbs / len(bullets) >= 0.5, f"{verbs} of {len(bullets)}",
            "Start bullets with verbs such as Built, Designed, Reduced, Led.", 1,
        ))
        quantified = sum(1 for b in bullets if _NUMBER_RE.search(b))
        checks.append(_check(
            "Quantified impact", quantified / len(bullets) >= 0.3, f"{quantified} of {len(bullets)} bullets contain numbers",
            "Add real numbers where you have them: users, latency, accuracy, team size, time saved.", 1,
        ))
    pipes = text.count("|") + text.count("\t")
    checks.append(_check(
        "Simple single-column layout", pipes <= 12, "tables or columns suspected" if pipes > 12 else "looks linear",
        "Avoid tables, text boxes and multi-column layouts; many ATS read them out of order.", 2,
    ))
    odd = sum(1 for ch in text if ord(ch) > 0x2FFF or 0xE000 <= ord(ch) <= 0xF8FF)
    checks.append(_check(
        "Standard characters", odd <= 5, f"{odd} unusual symbols/icons",
        "Replace icon fonts and emoji with plain text labels.", 1,
    ))
    return checks


def _posting_keywords(item: RssItem) -> list[str]:
    from_text = signals.extract_skills(f"{item.title}\n{item.summary or ''}\n{' '.join(item.tags or [])}")
    seen = {explain.canon(s) for s in from_text}
    extras = [t for t in (item.tags or []) if 2 < len(t) <= 30 and explain.canon(t) not in seen]
    return [*from_text, *extras[:8]]


def check_resume(profile: Profile | None, item: RssItem | None = None) -> dict:
    """ATS score and concrete changes. With `item`, also scores keyword coverage for that posting."""
    text = (profile.raw_text or "").strip() if profile else ""
    if not text:
        return {
            "has_resume": False,
            "message": "No resume text on file. Upload a text-based PDF resume first (scanned images can't be read by an ATS either).",
        }

    checks = _format_checks(text)
    total = sum(c["weight"] for c in checks)
    format_score = round(100 * sum(c["weight"] for c in checks if c["ok"]) / total)
    suggestions = [c["fix"] for c in checks if not c["ok"]]
    result: dict = {
        "has_resume": True,
        "format_score": format_score,
        "checks": [{k: v for k, v in c.items() if k != "weight"} for c in checks],
    }

    if item is None:
        result["overall_score"] = format_score
        result["suggestions"] = suggestions
        return result

    keywords = _posting_keywords(item)
    present = [k for k in keywords if _mentions(text, k) or _mentions(text, explain.canon(k))]
    missing = [k for k in keywords if k not in present]
    profile_has = {explain.canon(s) for s in explain.user_skills(profile)}
    # Skills the student already lists in their profile but the resume text never states plainly.
    stated_in_profile = [k for k in missing if explain.canon(k) in profile_has]
    truly_missing = [k for k in missing if k not in stated_in_profile]
    coverage = round(100 * len(present) / len(keywords)) if keywords else None

    title_words = [w for w in _WORD_RE.findall(item.title.lower()) if len(w) > 3]
    title_match = bool(title_words) and any(_mentions(text, w) for w in title_words)

    result.update(
        posting={"id": item.id, "title": item.title},
        keywords={"coverage": coverage, "matched": present, "missing": missing, "listed_in_profile_but_not_in_resume_text": stated_in_profile},
        job_title_words_in_resume=title_match,
    )
    kw_suggestions: list[str] = []
    if stated_in_profile:
        kw_suggestions.append(
            f"Your profile lists {', '.join(stated_in_profile)}, but the resume text never states it plainly. "
            "Add it to your Skills section and to the bullet where you used it."
        )
    if truly_missing:
        kw_suggestions.append(
            f"The posting asks for {', '.join(truly_missing[:8])}, which your resume doesn't mention. "
            "Add a keyword only if you genuinely have that skill; otherwise treat it as a gap to learn or a project to build."
        )
    if not title_match:
        kw_suggestions.append(
            f"Mirror the role title (\"{item.title}\") in your summary or objective line if it honestly describes you."
        )
    result["overall_score"] = round(0.6 * (coverage if coverage is not None else format_score) + 0.4 * format_score)
    result["suggestions"] = [*kw_suggestions, *suggestions]
    return result
