# file: phoneint/reputation/adapter.py
"""
Adapter interfaces for reputation lookups.

Adapters must be async and cancellable. They return structured `SearchResult`
entries that can be included in reports and used for scoring.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass(frozen=True, slots=True)
class SearchResult:
    """
    A single piece of evidence from a reputation/search adapter.

    Fields:
        title: Human-readable title (best-effort).
        url: Evidence URL (best-effort; may be a pseudo-URL for dataset matches).
        snippet: Short text excerpt/summary (best-effort).
        timestamp: When this result was fetched by phoneint.
        source: Adapter/source name (e.g., "duckduckgo", "public_scam_db").
    """

    title: str
    url: str
    snippet: str
    timestamp: datetime
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


class ReputationAdapter(ABC):
    """Base interface for reputation adapters."""

    name: str

    @abstractmethod
    async def check(self, e164: str, *, limit: int = 5) -> list[SearchResult]:
        """
        Check reputation/evidence for an E.164 phone number.

        Args:
            e164: E.164 number (e.g., +14155552671).
            limit: Max number of results.
        """

        raise NotImplementedError


class SearchAdapter(ReputationAdapter, ABC):
    """Base interface for adapters that can perform free-text search."""

    @abstractmethod
    async def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Search for a query string and return evidence results."""

        raise NotImplementedError

    async def check(self, e164: str, *, limit: int = 5) -> list[SearchResult]:
        # Default behavior: treat the number as the search query.
        return await self.search(e164, limit=limit)
