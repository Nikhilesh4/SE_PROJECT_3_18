"""
Per-category content filter for RSS entries.

is_opportunity_post() returns True ONLY if the entry looks like an actual
listing/opening — not a blog article, career-advice post, or event recap.

HACKATHON: strict two-signal model (action word + event/prize word).
RESEARCH: must contain PhD/postdoc/fellowship/scholarship/grant signals.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Shared article-rejection patterns (title-level)
# Applies to: job, internship, freelance, research
# ---------------------------------------------------------------------------

_ARTICLE_TITLE_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhow to\b",
        r"\btips (for|to|on)\b",
        r"\bguide (to|for|on)\b",
        r"\bbest practices?\b",
        r"\bbenefits of\b",
        r"\bways to\b",
        r"\bsteps to\b",
        r"\bthings (to|you|every)\b",
        r"\bwhy you should\b",
        r"\bwhat (is|are|to)\b",
        r"\bhow (does|do|can)\b",
        r"\bimprove your\b",
        r"\blearn (to|how)\b",
        r"\bskills (for|to|you need)\b",
        r"\binterview (tips|questions|prep)\b",
        r"\bresume (tips|writing|review)\b",
        r"\bcareer (advice|tips|growth|development|path)\b",
        r"\bwork-?life balance\b",
        r"\bpersonal (brand|development|growth)\b",
        r"\bmindfulness\b",
        r"\bproductivity (tips|hacks|tools)\b",
        r"\bsalary negotiat\b",
        r"\bnetworking (tips|strategies)\b",
        r"\bmotivation\b",
        r"\bsuccess stories?\b",
        r"\binspir\b",
        r"\bfreelance (advice|tips|guide|journey|life|career|marketing)\b",
        r"\bremote work (tips|guide|advice)\b",
        r"\bwork from home (tips|guide)\b",
        r"^\s*top\s+\d+\b",
        r"^\s*\d+\s+\w+\s+to\b",
    )
)

# ---------------------------------------------------------------------------
# RESEARCH — opportunity filter
# ---------------------------------------------------------------------------

# Reject: blog articles, news, general academic tips
_RESEARCH_REJECT_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhow to\b",
        r"\btips (for|on|to)\b",
        r"\bguide (to|for|on)\b",
        r"\bbest (journals?|practices?|tools?)\b",
        r"\blist of\b",
        r"\btop \d+\b",
        r"\bwhat (is|are)\b",
        r"\bwhy (you|researchers?|students?)\b",
        r"\bai plagiarism\b",
        r"\blearn(ing)? (to|how|about)\b",
        r"\beverything (you|to) (must |should )?know\b",
        r"\bai (tool|checker|detector)\b",
        r"\bcited by\b",
        r"\bimpact factor\b",
        r"\bsci.?indexed\b",
        r"\bjournal list\b",
        r"\bpublish(ing)? (in|your)\b",
        r"\bpaper (writing|submission|review)\b",
        r"\bthesis (writing|tips|guide)\b",
        r"\bcybersecurity\b",
        r"\bmachine learning in\b",
    )
)

# Allow: must match at least one research opportunity signal
_RESEARCH_ALLOW_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bphd (position|studentship|fellowship|scholarship|opening|vacancy|program|candidate)\b",
        r"\bphd student\b",
        r"\bpostdoc(toral)?\b",
        r"\bresearch (position|opening|vacancy|fellow|assistant|associate|intern|grant|award|chair)\b",
        r"\bfaculty position\b",
        r"\bprofessor(ship)?\b",
        r"\bresearcher (position|opening|vacancy)\b",
        r"\bscientist (position|opening)\b",
        r"\bjunior researcher\b",
        r"\bsenior researcher\b",
        r"\bfellowship\b",
        r"\bscholarship\b",
        r"\bgrant\b",
        r"\bfunded (position|phd|research|studentship|program)\b",
        r"\bstipend\b",
        r"\bfunding (opportunity|available|for)\b",
        r"\bbursary\b",
        r"\bstudy (abroad|in|opportunity)\b",
        r"\bexchange (program|opportunity)\b",
        r"\bapply (by|before|now|online|here)\b",
        r"\bapplication (deadline|open|window|period|invited)\b",
        r"\bcall for (applications?|proposals?|candidates?|researchers?)\b",
        r"\bdeadline\b",
        r"\bopening (for|in|at)\b",
        r"\bvacancy\b",
        r"\bwe are (recruiting|seeking|looking for)\b",
        r"\bjoin (our|the) (lab|group|team|program)\b",
        r"\brecruit(ing|ment)?\b",
        r"\bsummer (research|internship|program|school)\b",
        r"\bwinter (school|program)\b",
        r"\breu program\b",
        r"\bstudentship\b",
        r"\bdaad\b",
        r"\berasmus\b",
        r"\bfulbright\b",
        r"\bgatsby\b",
        r"\bwellcome\b",
        r"\bnsf (grant|fellowship)\b",
        r"\bnih (grant|fellowship)\b",
        r"\binternational (scholarship|fellowship|opportunity)\b",
    )
)

# ---------------------------------------------------------------------------
# HACKATHON — strict two-signal model
# ---------------------------------------------------------------------------

# Signal Group A: strong action / call-to-action words
_HACKATHON_ACTION_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bregist(er|ration|ered|rations?)\b",
        r"\bapply\b",
        r"\bapplication(s)? (open|close|due|deadline)\b",
        r"\bparticipat(e|ing|ion)\b",
        r"\bsubmit (your|a|an|now|project|solution|idea)\b",
        r"\bopen (for submissions?|for registration|now)\b",
        r"\bnow open\b",
        r"\bdeadline\b",
        r"\bsubmission deadline\b",
        r"\blast date (to|for)\b",
        r"\bapply (now|by|before|here|today)\b",
        r"\bjoin (us|the hackathon|the challenge|the competition|now)\b",
        r"\bsign.?up\b",
        r"\benroll(ment)?\b",
        r"\bcall for (participants?|submissions?|teams?|ideas?|hackers?)\b",
        r"\binvit(ing|ation|e) (teams?|developers?|hackers?|you)\b",
    )
)

# Signal Group B: event-context / prize / competition words
_HACKATHON_EVENT_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhackathon\b",
        r"\bchallenge\b",
        r"\bcompetition\b",
        r"\bcontest\b",
        r"\bsprint\b",
        r"\bjam\b",                         # game jam, hackjam
        r"\bprize(s| money| pool)?\b",
        r"\bcash prize\b",
        r"\btotal prize\b",
        r"\bwin(ners?)? \$",                 # "win $10,000"
        r"\$[\d,]+\s*(usd|prize|award)?\b",  # "$10,000 in prizes"
        r"\bhack\b",
        r"\bcode.?fest\b",
        r"\bdata.?thon\b",
        r"\bai.?challenge\b",
        r"\bbuildathon\b",
        r"\bideathon\b",
    )
)

# Hard-reject: past events, news articles, experience posts
_HACKATHON_REJECT_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # Past-event words
        r"\b(winners?|winning team)\b",
        r"\bwon\b",
        r"\brecap\b",
        r"\bhighlights?\b",
        r"\breview of\b",
        r"\bresults?\s+announced\b",
        r"\baward(s|ed|ing)?\b",
        r"\bcongratulations?\b",
        r"\bwrap[- ]?up\b",
        r"\bthank(s| you) (to|for)\b",
        r"\blook(ing)? back\b",
        # Experience / reflection posts
        r"\bi built\b",
        r"\bhow i built\b",
        r"\bi (learned?|discovered|realized)\b",
        r"\bwhat (hackathons?|the hackathon) taught me\b",
        r"\bmy (hackathon|experience|journey|story)\b",
        r"\b(lessons?|things?) (i )?(learned?|learned at)\b",
        r"\breflect(ions?|ing)?\b",
        r"\btakeaways?\b",
        r"\bpostmortem\b",
        r"\bproject showcase\b",
        # News / journalism patterns
        r"\bbrings\b",
        r"\bcloser to\b",
        r"\bshaped (your|my|the)\b",
        r"\b(effect|impact) of\b",
        r"\bthe (story|rise|future) of\b",
        r"\ba deep dive\b",
        r"\bpinnacle of\b",
        r"\bpowering (ai|the)\b",
        r"\bmakes (ai|the)\b",
        r"\bfuels?\b",
        r"\bexploring\b",
        r"\bbuilding (a|the|an) (frontend|backend|app|system|tool|agent|infrastructure|platform|pipeline|framework)\b",
        # Infrastructure / tutorial posts that mention participation coincidentally
        r"\binfrastructure\b",
        r"\bopen data\b",
        r"\bcommunity (engagement|building|collaboration)\b",
        r"\bsustainable\b",
        r"\bactually taught\b",
    )
)

# ---------------------------------------------------------------------------
# Job / Internship ALLOW patterns
# ---------------------------------------------------------------------------

_JOB_ALLOW_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bhiring\b",
        r"\bvacancy\b",
        r"\bvacancies\b",
        r"\bopening(s)?\b",
        r"\bjob (at|with|for|listing|post|title|offer)\b",
        r"\bposition(s)?\b",
        r"\brole(s)?\b",
        r"\bwe are (hiring|looking)\b",
        r"\bwe'?re (hiring|looking for)\b",
        r"\bjoin (our|us|the team)\b",
        r"\bapply (now|today|here|online)\b",
        r"\bjob description\b",
        r"\bfull[- ]?time\b",
        r"\bpart[- ]?time\b",
        r"\bremote\b",
        r"\bwork from home\b",
        r"\bfreelance (developer|designer|writer|engineer)\b",
        r"\bcontractor\b",
        r"\bsalary\b",
        r"\bctc\b",
        r"\blpa\b",
        r"\bstipend\b",
        r"\bpay(ment)?\b",
        r"\bcompensation\b",
        r"\bintern(ship)?\b",
        r"\bfresher(s)?\b",
        r"\bentry.?level\b",
        r"\bgraduate (role|position|job)\b",
        r"\b(software|backend|frontend|full.?stack|data|ml|ai|devops|cloud) (engineer|developer|intern)\b",
        r"\b(product|project|program) manager\b",
        r"\bdesigner\b",
        r"\banalyst\b",
        r"\bresearcher\b",
        r"\brecruit\b",
        r"\bcareers? at\b",
        r"\bcareers? page\b",
        r"\bjobs? at\b",
        r"\bopportunity\b",
        r"\bopportunities\b",
        r"\(remote\)",
        r"\(hybrid\)",
        r"\(on.?site\)",
    )
)

# ---------------------------------------------------------------------------
# Freelance ALLOW patterns
# ---------------------------------------------------------------------------

_FREELANCE_ALLOW_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bproject\b",
        r"\bbudget\b",
        r"\bbid\b",
        r"\bproposal\b",
        r"\bclient (needs?|want|is looking)\b",
        r"\blooking for (a )?freelancer\b",
        r"\bhire (a |an )?(freelancer|developer|designer|writer)\b",
        r"\bjob posting\b",
        r"\bcontract (work|job|position|opportunity)\b",
        r"\bfixed (price|rate)\b",
        r"\bhourly rate\b",
        r"\bper hour\b",
        r"\bwebsite (design|development|build)\b",
        r"\bapp (development|design|build)\b",
        r"\bwanted\b",
        r"\brequired\b",
        r"\bwe need\b",
        r"\bseeking\b",
        r"\bvacancy\b",
        r"\bopening\b",
        r"\b(wordpress|woocommerce|shopify|react|vue|angular|php|python|django|laravel|node) (developer|engineer)\b",
        r"\bfreelance (php|wordpress|web|app|mobile|react|python|design|content|copy)\b",
    )
)

# ---------------------------------------------------------------------------
# COURSE — enrollment / opening filter
# ---------------------------------------------------------------------------

# Reject: blog articles, opinion, news recaps, retrospectives
_COURSE_REJECT_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\breview\b",
        r"\bopinion\b",
        r"\bthoughts? on\b",
        r"\bmy (journey|story|experience)\b",
        r"\blessons? (i |learned?|from)\b",
        r"\bwhat (i|we) learned?\b",
        r"\byear in review\b",
        r"\b(roundup|wrap.?up|recap)\b",
        r"\bthe future of\b",
        r"\btrends? in\b",
        r"\bstate of (the )?\w+\b",
        r"\bprediction(s)?\b",
        r"\bwalk.?through\b",
        r"\bcheat.?sheet\b",
        r"\bcompare\b",
        r"\bversus\b",
        r"\b vs \b",
        r"\bchangelog\b",
        r"\bhow (coursera|edx|udemy|futurelearn|classcentral) works?\b",
        r"\bnew (feature|update|release|blog|post)\b",
    )
)

# Allow: must match at least one enrollment / opening signal
_COURSE_ALLOW_PATTERNS: tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        # Enrollment / sign-up signals
        r"\benroll(ment)?\b",
        r"\bregister\b",
        r"\bregistration\b",
        r"\bsign.?up\b",
        r"\bjoin (the )?(course|program|class|cohort|batch|bootcamp)\b",
        r"\bapply (now|today|here|online|by)\b",
        r"\bapplication (open|deadline)\b",
        # Free / discount signals (core to coupon-feed sources)
        r"\bfree (course|certificate|certification|access|enroll|class|training)\b",
        r"\b100% (off|free)\b",
        r"\bfree coupon\b",
        r"\bcoupon\b",
        r"\baudit(ing)? (this |for )?free\b",
        r"\baccess for free\b",
        r"\blimited (time|seats?|offer)\b",
        r"\bfull (course|access) free\b",
        # Timing / deadline signals
        r"\bdeadline\b",
        r"\bstart(s|ing|ed)? (on|from|in|this)\b",
        r"\bstart date\b",
        r"\bnow (available|open|live|accepting)\b",
        r"\bopen (for |now)?enrollment\b",
        r"\bopen (now|for students?)\b",
        r"\bnew course\b",
        r"\bnewly (added|available)\b",
        r"\bupcoming (course|cohort|class|batch)\b",
        r"\bregistration (open|deadline|closes?)\b",
        # MOOC / certification format signals
        r"\bmooc\b",
        r"\bcertificate program\b",
        r"\bcertification (course|program|exam|prep)\b",
        r"\bcohort\b",
        r"\bbatch\b",
        r"\bbootcamp\b",
        r"\bscholarship (available|for|open)\b",
        r"\blearn .{0,30} for free\b",
        r"\bfree .{0,30} course\b",
        r"\bgrab (this )?(course|certificate|deal)\b",
        r"\bseats? (available|limited|open)\b",
        r"\bget (this )?course free\b",
    )
)


def _match_any(patterns: tuple[re.Pattern, ...], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def is_opportunity_post(title: str, summary: str, category: str) -> bool:
    """
    Return True only if the RSS entry is a real opportunity — not an article,
    recap, or experience post.

    HACKATHON uses a strict two-signal model:
      - Must have a GROUP-A action word (register, apply, deadline, open for…)
      - AND a GROUP-B event/prize word (hackathon, competition, prize, $X…)
      - AND must NOT match any hard-reject pattern (recap, winners, "I built…")
    """
    combined = f"{title} {summary}"

    # ── Job / Internship ─────────────────────────────────────────────────
    if category in ("job", "internship", "freelance"):
        if _match_any(_ARTICLE_TITLE_PATTERNS, title):
            return False

    if category in ("job", "internship"):
        return _match_any(_JOB_ALLOW_PATTERNS, combined)

    if category == "freelance":
        return _match_any(_FREELANCE_ALLOW_PATTERNS, combined)

    # ── Hackathon (strict two-signal model) ──────────────────────────────
    if category == "hackathon":
        # Step 1: hard reject on the TITLE first (title is most reliable signal)
        if _match_any(_HACKATHON_REJECT_PATTERNS, title):
            return False
        # Step 2: hard reject on combined title+summary
        if _match_any(_HACKATHON_REJECT_PATTERNS, combined):
            return False
        # Step 3: must have BOTH an action word AND an event/prize word
        has_action = _match_any(_HACKATHON_ACTION_PATTERNS, combined)
        has_event  = _match_any(_HACKATHON_EVENT_PATTERNS, combined)
        return has_action and has_event

    if category == "research":
        if _match_any(_ARTICLE_TITLE_PATTERNS, title):
            return False
        if _match_any(_RESEARCH_REJECT_PATTERNS, title):
            return False
        return _match_any(_RESEARCH_ALLOW_PATTERNS, combined)

    # ── Course (enrollment / opening filter) ─────────────────────────────
    if category == "course":
        # Step 1: reject blog articles, opinion pieces, news
        if _match_any(_ARTICLE_TITLE_PATTERNS, title):
            return False
        if _match_any(_COURSE_REJECT_PATTERNS, title):
            return False
        # Step 2: must have at least one enrollment / opening signal
        return _match_any(_COURSE_ALLOW_PATTERNS, combined)

    return True
