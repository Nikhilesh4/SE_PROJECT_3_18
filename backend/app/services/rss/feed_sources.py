"""
All configured RSS sources for UniCompass.

ALL URLs below have been probe-tested and return HTTP 200.

HACKATHON NOTE
--------------
No major hackathon platform (Devpost, HackerEarth, Unstop, CTFtime, Codeforces)
provides a working public RSS feed — they all block bots or return 404/403.
The hackathon sources below are verified-working feeds that publish hackathon
announcements, competition launches and challenge listings. The content filter
(filter.py) ensures only posts about active/upcoming events pass through.

INTERNSHIP NOTE
---------------
Dedicated internship-specific RSS endpoints are rare. The sources below include
general remote-job boards filtered to internship/entry-level posts plus HN Jobs,
with the content filter rejecting blog articles and keeping only real listings.

FREELANCE NOTE
--------------
PeoplePerHour and Freelancer.com no longer expose public RSS (both 404).
The three sources below are verified project-listing boards.
"""

from dataclasses import dataclass
from app.schemas.rss_item import OpportunityCategory

@dataclass(frozen=True)
class FeedSource:
    url: str
    category: OpportunityCategory
    source_name: str


FEED_SOURCES: tuple[FeedSource, ...] = (
    # ── INTERNSHIPS ────────────────────────────────────────────────────────
    # Verified 200 ✓
    FeedSource(
        "https://remoteok.com/remote-intern-jobs.rss",
        "internship",
        "RemoteOK – Internships",
    ),
    FeedSource(
        "https://jobicy.com/?feed=job_feed&job_types=internship",
        "internship",
        "Jobicy – Internships",
    ),
    FeedSource(
        "https://remotive.com/remote-jobs/feed",
        "internship",
        "Remotive – Remote Jobs",
    ),
    FeedSource(
        "https://hnrss.org/jobs",
        "internship",
        "Hacker News – Who is Hiring",
    ),
    FeedSource(
        "https://weworkremotely.com/remote-jobs.rss",
        "internship",
        "We Work Remotely (all — intern filter)",
    ),

    # ── JOBS ───────────────────────────────────────────────────────────────
    # Verified 200 ✓
    FeedSource("https://remoteok.com/remote-jobs.rss", "job", "RemoteOK"),
    FeedSource("https://remoteok.com/remote-dev-jobs.rss", "job", "RemoteOK – Dev"),
    FeedSource("https://remoteok.com/remote-design-jobs.rss", "job", "RemoteOK – Design"),
    FeedSource("https://weworkremotely.com/remote-jobs.rss", "job", "We Work Remotely"),
    FeedSource(
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "job",
        "We Work Remotely – Programming",
    ),
    FeedSource(
        "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
        "job",
        "We Work Remotely – Back-End",
    ),
    FeedSource(
        "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
        "job",
        "We Work Remotely – Front-End",
    ),
    FeedSource(
        "https://weworkremotely.com/categories/remote-design-jobs.rss",
        "job",
        "We Work Remotely – Design",
    ),
    FeedSource("https://jobicy.com/?feed=job_feed", "job", "Jobicy"),
    FeedSource("https://hnrss.org/jobs", "job", "Hacker News – Jobs"),
    FeedSource("https://remotive.com/remote-jobs/feed", "job", "Remotive"),

    # ── HACKATHONS ─────────────────────────────────────────────────────────
    # All verified 200 ✓. Content filter allows only upcoming-event posts.
    FeedSource(
        "https://news.mlh.io/posts/feed",
        "hackathon",
        "Major League Hacking",
    ),
    FeedSource(
        "https://dev.to/feed/tag/hackathon",
        "hackathon",
        "DEV Community – Hackathon",
    ),
    FeedSource(
        "https://dev.to/feed/tag/competition",
        "hackathon",
        "DEV Community – Competition",
    ),
    FeedSource(
        "https://www.topcoder.com/blog/feed/",
        "hackathon",
        "Topcoder Challenges Blog",
    ),
    FeedSource(
        "https://www.hackerrank.com/blog/feed",
        "hackathon",
        "HackerRank Challenges",
    ),
    FeedSource(
        "https://techcrunch.com/tag/hackathon/feed/",
        "hackathon",
        "TechCrunch – Hackathon",
    ),

    # ── RESEARCH ───────────────────────────────────────────────────────────
    # All verified 200 ✓ — actual position/fellowship/scholarship listings
    FeedSource(
        "https://www.jobs.ac.uk/search/rss?q=phd+fellowship",
        "research",
        "jobs.ac.uk – PhD & Fellowships",
    ),
    FeedSource(
        "https://www.jobs.ac.uk/search/rss?q=postdoc+research+position",
        "research",
        "jobs.ac.uk – Postdoc Positions",
    ),
    FeedSource(
        "https://www.jobs.ac.uk/search/rss?q=research+internship+studentship",
        "research",
        "jobs.ac.uk – Research Internships",
    ),
    FeedSource(
        "https://opportunitydesk.org/feed/",
        "research",
        "Opportunity Desk",
    ),
    FeedSource(
        "https://youthop.com/scholarships/feed",
        "research",
        "YouthOp – Scholarships",
    ),
    FeedSource(
        "https://scholarshipscorner.website/feed/",
        "research",
        "Scholarships Corner",
    ),
    FeedSource(
        "https://jobs.newscientist.com/jobs.rss",
        "research",
        "New Scientist – Science Jobs",
    ),
    FeedSource(
        "https://www.opportunitiesforafricans.com/feed/",
        "research",
        "Opportunities for Africans",
    ),
    FeedSource(
        "https://www.studying-in-germany.org/feed/",
        "research",
        "Studying in Germany – Scholarships",
    ),

    # ── FREELANCE ──────────────────────────────────────────────────────────
    # Verified 200 ✓ (PeoplePerHour & Freelancer.com both 404 — removed)
    FeedSource(
        "https://www.smashingmagazine.com/jobs/feed/",
        "freelance",
        "Smashing Magazine Jobs",
    ),
    FeedSource("https://jobs.wordpress.net/feed/", "freelance", "WordPress Jobs"),
    FeedSource("https://dribbble.com/jobs.rss", "freelance", "Dribbble Jobs"),
    FeedSource(
        "https://remoteok.com/remote-freelance-jobs.rss",
        "freelance",
        "RemoteOK – Freelance",
    ),

    # ── COURSES ────────────────────────────────────────────────────────────
    # COURSE NOTE
    # -----------
    # Only feeds that publish new enrollment listings, free-coupon drops, or
    # upcoming batch/cohort openings are included here.  Blog posts, reviews,
    # opinion pieces, and news articles are rejected by the course filter in
    # filter.py (is_opportunity_post, category="course").
    #
    # Sources that work well:
    #   - Class Central: aggregates enrollment-open announcements for MOOCs
    #     across Coursera, edX, FutureLearn, Udemy, etc.
    #   - freeCodeCamp News: publishes new free curriculum and course launches
    #   - Real Python: publishes new tutorial/course release announcements
    #   - Coursera Blog: publishes new course & certificate program launches
    #   - edX Blog: publishes new program and course open-enrollment posts
    FeedSource(
        "https://www.classcentral.com/report/feed/",
        "course",
        "Class Central – MOOC Listings",
    ),
    FeedSource(
        "https://www.freecodecamp.org/news/rss/",
        "course",
        "freeCodeCamp – Free Courses",
    ),
    FeedSource(
        "https://realpython.com/atom.xml",
        "course",
        "Real Python – Course Releases",
    ),
    FeedSource(
        "https://blog.coursera.org/feed/",
        "course",
        "Coursera Blog – New Programs",
    ),
    FeedSource(
        "https://blog.edx.org/feed/",
        "course",
        "edX Blog – New Courses",
    ),
    FeedSource(
        "https://ocw.mit.edu/rss/new_ocw_courses.xml",
        "course",
        "MIT OpenCourseWare – New Courses",
    ),
    FeedSource(
        "https://blog.udacity.com/feed",
        "course",
        "Udacity Blog – New Nanodegrees",
    ),
    FeedSource(
        "https://www.datacamp.com/blog/rss.xml",
        "course",
        "DataCamp – New Courses & Tracks",
    ),
    FeedSource(
        "https://www.simplilearn.com/resources/rss.xml",
        "course",
        "Simplilearn – Free Courses",
    ),
    FeedSource(
        "https://alison.com/blog/rss",
        "course",
        "Alison – Free Online Courses",
    ),
    FeedSource(
        "https://learndigital.withgoogle.com/digitalgarage/rss.xml",
        "course",
        "Google Digital Garage – Free Courses",
    ),
    FeedSource(
        "https://www.futurelearn.com/info/blog/feed",
        "course",
        "FutureLearn – New Programs",
    ),
)
