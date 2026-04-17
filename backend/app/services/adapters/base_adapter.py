"""Abstract base class for all opportunity-source adapters (Adapter pattern)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas.rss_item import NormalizedRssItem


class OpportunityAdapter(ABC):
    """
    Common interface for every external data source.

    Each adapter fetches opportunities from its source and normalizes them
    into ``NormalizedRssItem`` objects so the rest of the pipeline
    (aggregator, cache, worker) can treat every source uniformly.
    """

    @abstractmethod
    def fetch_opportunities(
        self,
        *,
        keywords: str = "",
        location: str = "",
        page: int = 1,
        limit: int = 20,
    ) -> list[NormalizedRssItem]:
        """Return normalized items from the external source."""
        ...
