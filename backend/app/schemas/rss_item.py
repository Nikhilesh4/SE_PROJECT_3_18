"""Common schema for items ingested from any RSS/Atom source."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Aligned with UniCompass opportunity kinds (+ job, freelance from RSS corpus)
OpportunityCategory = Literal[
    "internship",
    "hackathon",
    "research",
    "course",
    "job",
    "freelance",
]


class NormalizedRssItem(BaseModel):
    """Unified shape produced from every feed entry, regardless of origin."""

    title: str
    url: str
    summary: str = ""
    published_at: datetime | None = None
    category: str
    source_name: str
    feed_url: str
    tags: list[str] = Field(default_factory=list)
    author: str | None = None
    guid: str | None = None

    model_config = {"from_attributes": True}


class FeedSourceStatus(BaseModel):
    """Per-feed fetch outcome for debugging and UI summaries."""

    feed_url: str
    category: str
    source_name: str
    ok: bool
    http_status: int | None = None
    error: str | None = None
    entries_fetched: int = 0
    items_normalized: int = 0


class RssAggregationResponse(BaseModel):
    """API payload: all normalized items plus source-level status."""

    items: list[NormalizedRssItem]
    sources: list[FeedSourceStatus]
    total_items: int
    fetched_at: datetime
