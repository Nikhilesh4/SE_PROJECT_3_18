"""Pick which tool definitions to send with each model request.

All ~27 tool definitions cost about 3,500 tokens, and the whole conversation is re-sent every
tool round. On a small token budget (Groq's free tier is 8k tokens/minute) that is most of
the allowance, so each request carries only the tools the message plausibly needs.

This only limits what the model is *offered*. Dispatch is unchanged, and the selection is
recomputed every round, so a tool the model already used stays available for the rest of the run.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.services.agent.providers import ToolSpec

CORE = ("search_opportunities", "get_opportunity", "get_profile")

# group → (keyword regex over the student's message, tool names)
GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "posting_text": (
        r"pay|stipend|salary|eligib|requirement|location|remote|fee|apply|deadline|what does|says?|state[sd]?|"
        r"benefit|visa|duration|compare|versus|\bvs\b|resume|cv\b|match",
        ("search_posting_text", "find_in_posting", "compare_opportunities", "match_resume_to_opportunity"),
    ),
    "bookmarks": (r"bookmark|\bsave|saved|unsave|favou?rite", ("list_bookmarks", "bookmark_opportunity", "remove_bookmark")),
    "deadlines": (r"deadline|closing|due\b|soon|expir|this week|next week|upcoming", ("upcoming_deadlines",)),
    "tracker": (
        r"application|applied|apply|interview|offer|reject|kanban|track|status|pipeline",
        ("list_applications", "update_application"),
    ),
    "missions": (
        r"notification|notify|alert|mission|daily|watch|remind|standup|stand-up|digest|this week|what should i do|next steps?|priorit",
        ("get_notifications", "list_missions", "create_mission", "run_mission", "career_standup"),
    ),
    "insights": (
        r"\bwhy\b|\bfit|gap|skill|scam|legit|eligib|explain|trend|demand|filter|paid|company|startup|"
        r"closing soon|minimum|at least",
        ("explain_opportunity", "search_with_filters", "skill_demand_trends", "company_brief", "suggest_projects"),
    ),
    "pay": (
        r"\bpay\b|\bpaid|salary|salaries|stipend|earn|compensation|how much|typical|average|going rate",
        ("pay_insights",),
    ),
    "coach": (
        r"interview|outreach|email|cold|referral|linkedin|cover letter|research|professor|lab\b|project|"
        r"note|memory|remember|follow.?up",
        ("interview_questions", "draft_outreach", "research_scout", "search_my_notes", "suggest_projects"),
    ),
    "profile": (r"profile|resume|\bcv\b|interest|update my|change my|add .* skill", ("update_profile",)),
    "ats": (
        r"\bats\b|applicant tracking|resume|\bcv\b|keyword|tailor|optimi[sz]e|improve my|what.* (change|fix)|match (the|this|that) (job|role|posting)",
        ("ats_check_resume", "match_resume_to_opportunity", "get_opportunity"),
    ),
}

# Offered when the message matches nothing: the commonly useful lookups.
DEFAULT_EXTRA = ("search_posting_text", "find_in_posting", "search_with_filters", "upcoming_deadlines")


def select_tools(specs: Iterable[ToolSpec], user_text: str, used: Iterable[str] = ()) -> list[ToolSpec]:
    """Return the subset of `specs` to offer, preserving the original order."""
    specs = list(specs)
    text = (user_text or "").lower()
    wanted: set[str] = set(CORE) | set(used)
    matched = False
    for pattern, names in GROUPS.values():
        if re.search(pattern, text):
            wanted.update(names)
            matched = True
    if not matched:
        wanted.update(DEFAULT_EXTRA)
    # External MCP tools (`server__tool`) were enabled on purpose; always offer them.
    return [s for s in specs if s.name in wanted or "__" in s.name]
