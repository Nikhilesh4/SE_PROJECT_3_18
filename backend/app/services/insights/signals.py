"""Heuristic signals read from a posting's text: scam risk, stipend, remote, eligibility, skills.

Pure functions, no I/O — cheap enough to run on every posting at request time
and in the verifier. They are heuristics: they raise flags for a human to look
at, they never delete or hide a posting on their own.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field

# ── Scam detection ───────────────────────────────────────────────────────────

_SCAM_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    (
        "asks-for-fee",
        re.compile(
            r"(registration|security|training|processing|joining|application|refundable)\s+(fee|deposit|charges?)"
            r"|pay\s+(a\s+)?(fee|deposit)|(send|transfer)\s+(money|payment)",
            re.I,
        ),
        "Asks the applicant to pay a fee or deposit",
    ),
    (
        "messaging-app-only",
        re.compile(r"(whats\s?app|telegram|signal)\s*(only|number|me|:|us|group)|contact\s+(us\s+)?(on|via)\s+(whats\s?app|telegram)", re.I),
        "Contact only through WhatsApp/Telegram",
    ),
    (
        "too-good-to-be-true",
        re.compile(r"(earn|make)\s+(up\s+to\s+)?[₹$]?\s?\d[\d,]*\s*(/|per)\s*(day|hour)|guaranteed\s+(job|income|placement)|no\s+experience\s+(needed|required).{0,40}(high|huge)\s+(pay|salary)|work\s+from\s+home.{0,30}(daily|weekly)\s+payout", re.I),
        "Unrealistic pay or guaranteed outcome",
    ),
    (
        "personal-financial-info",
        re.compile(r"(bank\s+account|aadhaar|aadhar|ssn|social\s+security|credit\s+card)\s+(number|details|info)", re.I),
        "Requests sensitive personal or bank details up front",
    ),
    (
        "free-email-domain",
        re.compile(r"\b[\w.+-]+@(gmail|yahoo|outlook|hotmail|rediffmail)\.com\b", re.I),
        "Applications go to a free personal email address",
    ),
)


@dataclass
class ScamAssessment:
    score: int  # 0–100, higher = riskier
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    @property
    def risky(self) -> bool:
        return self.score >= 40


def assess_scam_risk(title: str, summary: str, url: str = "") -> ScamAssessment:
    text = f"{title}\n{summary}"
    flags: list[str] = []
    reasons: list[str] = []
    score = 0
    weights = {"asks-for-fee": 60, "personal-financial-info": 50, "messaging-app-only": 35,
               "too-good-to-be-true": 35, "free-email-domain": 15}
    for flag, pattern, reason in _SCAM_RULES:
        if pattern.search(text):
            flags.append(flag)
            reasons.append(reason)
            score += weights[flag]
    if url and re.search(r"(bit\.ly|tinyurl\.com|t\.me/|wa\.me/)", url, re.I):
        flags.append("shortened-or-chat-link")
        reasons.append("Link is a URL shortener or chat invite")
        score += 25
    return ScamAssessment(min(score, 100), reasons, flags)


# ── Stipend ──────────────────────────────────────────────────────────────────

_CURRENCY = r"(?P<cur>₹|rs\.?|inr|\$|usd|€|eur|£|gbp)"
_NUM = r"(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s?(?P<mult>k|lpa|lakhs?|l)?"
_PERIOD = r"(?:\s*(?:/|per|a)\s*(?P<per>month|mo|year|yr|annum|week|hour|hr|day))?"
_STIPEND_RE = re.compile(rf"{_CURRENCY}\s?{_NUM}{_PERIOD}", re.I)
_PER_MONTH = {"month": 1, "mo": 1, "year": 1 / 12, "yr": 1 / 12, "annum": 1 / 12, "week": 4.33, "hour": 160, "hr": 160, "day": 22}
_INR_MARKERS = {"₹", "rs", "rs.", "inr"}
_TO_INR = {"₹": 1, "rs": 1, "rs.": 1, "inr": 1, "$": 83, "usd": 83, "€": 90, "eur": 90, "£": 105, "gbp": 105}


def extract_stipend(text: str) -> dict | None:
    """First stated amount, normalised to INR per month, or None.

    Returns {"amount": 25000.0, "currency": "INR", "period": "month", "raw": "₹25,000/month"}.
    """
    for m in _STIPEND_RE.finditer(text or ""):
        try:
            num = float(m.group("num").replace(",", ""))
        except ValueError:
            continue
        mult = (m.group("mult") or "").lower()
        cur = m.group("cur").lower()
        if mult == "k":
            if num < 1_000:  # "70,000 K" is a typo for 70k, not 70 million
                num *= 1_000
        elif mult in ("lpa", "lakh", "lakhs", "l"):
            num *= 100_000
        period = (m.group("per") or "").lower()
        if not period and mult == "lpa":
            period = "year"
        if num < 1_000 and not period and not mult:
            continue  # a bare "$100" or "$5" is a prize or price, not a stipend
        if not period:
            # No period stated: a big bare number is a yearly salary ("$120k"), a smaller one a monthly stipend.
            annual_from = 300_000 if cur in _INR_MARKERS else 15_000
            period = "year" if num >= annual_from else "month"
        per_month = num * _PER_MONTH.get(period, 1)
        inr = per_month * _TO_INR.get(cur, 1)
        return {"amount": round(inr, 2), "currency": "INR", "period": "month", "raw": m.group(0).strip()}
    return None


# Pay stats leave out categories whose amounts are not pay (prize pools, course fees) and implausible values.
STIPEND_EXCLUDED_CATEGORIES = frozenset({"hackathon", "course"})
STIPEND_SANE_RANGE = (3_000.0, 5_000_000.0)  # INR per month


def stipend_in_range(amount: float) -> bool:
    return STIPEND_SANE_RANGE[0] <= amount <= STIPEND_SANE_RANGE[1]


def summarize_amounts(values: list[float]) -> dict | None:
    """count, quartiles, median, min and max of INR/month amounts, or None for an empty list."""
    vals = sorted(values)
    if not vals:
        return None
    n = len(vals)
    if n >= 4:
        q1, _, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    else:
        q1, q3 = vals[0], vals[-1]
    return {"count": n, "p25": round(q1), "median": round(statistics.median(vals)), "p75": round(q3),
            "min": round(vals[0]), "max": round(vals[-1])}


# ── Remote / location ────────────────────────────────────────────────────────

def detect_remote(title: str, summary: str, tags: list[str] | None = None) -> bool:
    text = f"{title} {summary} {' '.join(tags or [])}".lower()
    if re.search(r"\b(on-?site|in-?office|onsite only)\b", text) and not re.search(r"\bremote\b|work from home|\bwfh\b", text):
        return False
    return bool(re.search(r"\bremote(ly)?\b|work from home|\bwfh\b|anywhere in the world|distributed team", text))


# ── Eligibility ──────────────────────────────────────────────────────────────

@dataclass
class EligibilityRules:
    years: list[int] = field(default_factory=list)        # graduation / study years that qualify
    min_cgpa: float | None = None
    branches: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.years or self.min_cgpa or self.branches or self.countries)


_BRANCHES = ("computer science", "cse", "information technology", "electronics", "ece", "electrical", "mechanical", "civil", "mathematics", "statistics", "data science")


def parse_eligibility(text: str) -> EligibilityRules:
    rules = EligibilityRules()
    t = text or ""
    for m in re.finditer(r"(?:batch|class|graduat\w+|pass(?:ing|ed)?\s*out)\s*(?:of|in|year)?\s*[:\-]?\s*((?:20\d\d)(?:\s*(?:,|/|and|or|&)\s*20\d\d)*)", t, re.I):
        rules.years += [int(y) for y in re.findall(r"20\d\d", m.group(1))]
    if re.search(r"final[- ]year|pre[- ]final", t, re.I):
        rules.notes.append("Targets final-year / pre-final-year students")
    m = re.search(r"(?:cgpa|gpa)\s*(?:of|>=|≥|above|min(?:imum)?)?\s*[:\-]?\s*(\d(?:\.\d+)?)\s*(?:\+|and above|or above)?", t, re.I)
    if m:
        value = float(m.group(1))
        if 4 <= value <= 10:
            rules.min_cgpa = value
    low = t.lower()
    rules.branches = sorted({b for b in _BRANCHES if re.search(rf"\b{re.escape(b)}\b", low)})
    m = re.search(r"(?:open to|only for|must be (?:based )?in|residents? of|eligible in)\s+([A-Z][A-Za-z ]{2,30})", t)
    if m:
        rules.countries.append(m.group(1).strip())
    rules.years = sorted(set(rules.years))
    return rules


def check_eligibility(rules: EligibilityRules, *, grad_year: int | None = None, cgpa: float | None = None) -> list[str]:
    """Human-readable reasons the user may NOT qualify (empty = no known blocker)."""
    problems: list[str] = []
    if rules.years and grad_year and grad_year not in rules.years:
        problems.append(f"Open to graduating class of {', '.join(map(str, rules.years))}; you are {grad_year}")
    if rules.min_cgpa and cgpa is not None and cgpa < rules.min_cgpa:
        problems.append(f"Requires CGPA ≥ {rules.min_cgpa}; yours is {cgpa}")
    return problems


# ── Skills mentioned in a posting ────────────────────────────────────────────

KNOWN_SKILLS = (
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "golang", "rust", "kotlin", "swift", "ruby", "php", "scala", "sql", "nosql",
    "react", "next.js", "node.js", "angular", "vue", "django", "flask", "fastapi", "spring", "express", ".net",
    "docker", "kubernetes", "aws", "azure", "gcp", "terraform", "linux", "git", "ci/cd", "jenkins",
    "machine learning", "deep learning", "nlp", "computer vision", "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "spark", "hadoop",
    "postgresql", "mysql", "mongodb", "redis", "kafka", "graphql", "rest", "html", "css", "tailwind",
    "android", "ios", "flutter", "react native", "figma", "tableau", "power bi", "excel", "llm", "rag", "devops", "cybersecurity", "blockchain",
)


def extract_skills(text: str) -> list[str]:
    """Known skills mentioned in `text`, in a stable order."""
    low = (text or "").lower()
    found = []
    for skill in KNOWN_SKILLS:
        pattern = rf"(?<![a-z0-9+#.]){re.escape(skill)}(?![a-z0-9+#])"
        if re.search(pattern, low):
            found.append(skill)
    return found
