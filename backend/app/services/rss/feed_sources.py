"""
All configured RSS sources for UniCompass (mirrors project validate_feeds.py).

Each tuple: (feed_url, category, source_display_name).
"""

from dataclasses import dataclass

from app.schemas.rss_item import OpportunityCategory


@dataclass(frozen=True)
class FeedSource:
    url: str
    category: OpportunityCategory
    source_name: str


FEED_SOURCES: tuple[FeedSource, ...] = (
    # --- INTERNSHIPS ---
    FeedSource("https://blog.internshala.com/feed/", "internship", "Internshala Blog"),
    FeedSource("https://www.mindler.com/blog/feed/", "internship", "Mindler"),
    FeedSource(
        "https://www.cheggindia.com/career-guidance-type/career-advice/feed/",
        "internship",
        "Chegg India",
    ),
    FeedSource("https://fresherblog.com/feed/", "internship", "Fresher Blog"),
    FeedSource("https://www.getsetresumes.com/blog/feed/", "internship", "GetSetResumes"),
    FeedSource("https://simplylifetips.com/career/feed/", "internship", "Simply Life Tips (Career)"),
    # --- HACKATHONS ---
    FeedSource(
        "https://www.microsoft.com/en-us/garage/blog/category/hackathons/feed/",
        "hackathon",
        "Microsoft Garage",
    ),
    FeedSource(
        "https://developer.nvidia.com/blog/tag/hackathon/feed/",
        "hackathon",
        "NVIDIA Developer Blog",
    ),
    FeedSource("https://cs.utdallas.edu/category/hackathon/feed/", "hackathon", "UT Dallas CS"),
    FeedSource(
        "https://www.hackathonsinternational.com/blog-feed.xml",
        "hackathon",
        "Hackathons International",
    ),
    FeedSource("https://www.hackthehub.com/feed/", "hackathon", "Hack The Hub"),
    FeedSource("https://tips.hackathon.com/article/rss.xml", "hackathon", "Tips.Hackathon.com"),
    FeedSource("https://news.mlh.io/posts/feed", "hackathon", "Major League Hacking"),
    FeedSource(
        "https://eship.cornell.edu/category/hackathon/feed/",
        "hackathon",
        "Cornell Entrepreneurship",
    ),
    # --- RESEARCH ---
    FeedSource("https://export.arxiv.org/rss/cs.CL", "research", "arXiv (cs.CL)"),
    FeedSource("https://www.ilovephd.com/feed/", "research", "iLovePhD"),
    FeedSource("https://thesiswhisperer.com/feed/", "research", "Thesis Whisperer"),
    FeedSource("https://researchwhisperer.org/feed/", "research", "Research Whisperer"),
    # --- COURSES ---
    FeedSource("https://www.classcentral.com/report/feed/", "course", "Class Central"),
    FeedSource("https://blog.coursera.org/feed/", "course", "Coursera Blog"),
    FeedSource("https://www.hackerrank.com/blog/feed", "course", "HackerRank Blog"),
    FeedSource("https://hackernoon.com/feed", "course", "HackerNoon"),
    # --- JOBS ---
    FeedSource("https://remoteok.com/remote-jobs.rss", "job", "RemoteOK"),
    FeedSource("https://weworkremotely.com/remote-jobs.rss", "job", "We Work Remotely"),
    FeedSource(
        "https://weworkremotely.com/categories/remote-programming-jobs.rss",
        "job",
        "We Work Remotely (Programming)",
    ),
    FeedSource("https://jobicy.com/?feed=job_feed", "job", "Jobicy"),
    FeedSource("https://hnrss.org/jobs", "job", "Hacker News (Who is hiring)"),
    FeedSource("https://dailyremote.com/remote-work-blog/feed/", "job", "DailyRemote (blog)"),
    FeedSource("https://nodesk.substack.com/feed", "job", "NoDesk (Substack)"),
    FeedSource(
        "https://blog.springworks.in/category/remote-work/feed/",
        "job",
        "Springworks (remote work, India)",
    ),
    FeedSource("https://www.borderlessmind.com/feed/", "job", "BorderlessMind"),
    # --- FREELANCE ---
    FeedSource("https://www.reddit.com/r/forhire/.rss", "freelance", "Reddit r/forhire"),
    FeedSource("https://www.reddit.com/r/freelance/.rss", "freelance", "Reddit r/freelance"),
    FeedSource("https://blog.freelancersunion.org/feed/", "freelance", "Freelancers Union Blog"),
    FeedSource("https://millo.co/feed", "freelance", "Millo"),
    FeedSource("https://beafreelanceblogger.com/feed/", "freelance", "Be a Freelance Blogger"),
)
