from app.services.agent.providers import ToolSpec
from app.services.agent.tool_select import CORE, select_tools

NAMES = [
    "search_opportunities", "get_opportunity", "upcoming_deadlines", "search_posting_text", "find_in_posting",
    "compare_opportunities", "match_resume_to_opportunity", "list_bookmarks", "bookmark_opportunity",
    "remove_bookmark", "list_applications", "update_application", "get_notifications", "list_missions",
    "create_mission", "run_mission", "explain_opportunity", "search_with_filters", "skill_demand_trends", "pay_insights",
    "company_brief", "suggest_projects", "interview_questions", "draft_outreach", "research_scout",
    "search_my_notes", "ats_check_resume", "career_standup", "get_profile", "update_profile", "gcal__create-event",
]
SPECS = [ToolSpec(n, "d", {}) for n in NAMES]


def names(text, used=()):
    return {s.name for s in select_tools(SPECS, text, used)}


def test_core_and_external_tools_always_offered():
    got = names("hello there")
    assert set(CORE) <= got and "gcal__create-event" in got


def test_unmatched_message_gets_default_lookups_not_everything():
    got = names("hello there")
    assert "search_posting_text" in got and "draft_outreach" not in got and len(got) < len(NAMES) - 10


def test_bookmark_and_tracker_requests_pull_their_tools():
    assert {"bookmark_opportunity", "list_bookmarks"} <= names("bookmark the second one")
    assert {"update_application", "list_applications"} <= names("I applied to Upstart, move it to interview")


def test_coach_and_missions():
    assert "draft_outreach" in names("write a cold email to the recruiter")
    assert {"create_mission", "run_mission"} <= names("watch for new remote ML internships daily")


def test_tools_already_used_stay_available():
    assert "draft_outreach" in names("hello there", used={"draft_outreach"})


def test_order_is_preserved_and_unknown_used_names_are_ignored():
    got = [s.name for s in select_tools(SPECS, "bookmark this", {"not_a_tool"})]
    assert got == [n for n in NAMES if n in set(got)]


def test_selection_cuts_the_definitions_sent():
    assert len(select_tools(SPECS, "what is the stipend?")) <= 12


def test_standup_questions_pull_the_standup_tool():
    assert "career_standup" in names("what should I do this week?")
    assert "career_standup" in names("give me my weekly standup")


def test_pay_questions_pull_pay_insights():
    assert "pay_insights" in names("how much do ML internships pay?")
    assert "pay_insights" in names("what is the typical salary for devops")


def test_ats_requests_offer_the_ats_tool():
    assert "ats_check_resume" in names("check the ATS score of my resume for this job")
    assert "ats_check_resume" in names("what should I change in my resume to match this role?")
