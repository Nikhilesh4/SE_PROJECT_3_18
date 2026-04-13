"""Per-category TTL configuration for RSS feed refresh (Strategy pattern)."""

from __future__ import annotations

# TTL in minutes for each opportunity category.
# Faster-changing sources get shorter TTLs.
CATEGORY_TTL_MINUTES: dict[str, int] = {
    "job": 60,         # 1 hour  — job listings change frequently
    "freelance": 120,  # 2 hours — moderate churn
    "internship": 180, # 3 hours — updated a few times daily
    "hackathon": 360,  # 6 hours — events don't change rapidly
    "research": 360,   # 6 hours — arXiv daily updates
    "course": 720,     # 12 hours — course blogs update infrequently
}

DEFAULT_TTL_MINUTES: int = 120  # fallback for unknown categories


def get_ttl_minutes(category: str) -> int:
    """Return the refresh TTL for a given category."""
    return CATEGORY_TTL_MINUTES.get(category, DEFAULT_TTL_MINUTES)
