"""Contracts and basic DTOs for owner intelligence."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

OwnershipType = Literal["business", "individual", "voip", "unknown"]

class LegalBasis(TypedDict, total=False):
    purpose: str
    consent_obtained: bool


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class OwnerAssociation:
    source: str
    url: str | None
    snippet: str
    label: str
    timestamp: datetime
    
    def to_dict(self) -> dict[str, str | None]:
        return {
            "source": self.source,
            "url": self.url,
            "snippet": self.snippet,
            "label": self.label,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass(frozen=True)
class OwnerPII:
    name: str
    source: str
    owner_category: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "source": self.source,
            "owner_category": self.owner_category,
        }


@dataclass(frozen=True)
class OwnerAdapterResult:
    associations: list[OwnerAssociation]
    pii: OwnerPII | None = None


@dataclass(frozen=True)
class OwnerAuditRecord:
    adapter: str
    time: datetime
    legal_basis: dict[str, Any]
    caller: str
    result: str


@dataclass(frozen=True)
class OwnerIntelResult:
    ownership_type: OwnershipType
    associations: list[OwnerAssociation]
    signals: dict[str, Any]
    confidence_score: int
    confidence_breakdown: list[dict[str, Any]]
    pii_allowed: bool
    pii: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ownership_type": self.ownership_type,
            "associations": [
                {
                    "source": assoc.source,
                    "url": assoc.url,
                    "snippet": assoc.snippet,
                    "label": assoc.label,
                    "timestamp": assoc.timestamp.isoformat(),
                }
                for assoc in self.associations
            ],
            "signals": self.signals,
            "confidence_score": self.confidence_score,
            "confidence_breakdown": self.confidence_breakdown,
            "pii_allowed": self.pii_allowed,
            "pii": self.pii,
        }


class OwnerAdapter(ABC):
    """Base interface for owner-intel adapters."""

    name: str
    pii_capable: bool

    @abstractmethod
    async def lookup_owner(
        self,
        e164: str,
        *,
        legal_basis: dict[str, Any] | None,
        limit: int = 5,
        caller: str | None = None,
    ) -> OwnerAdapterResult:
        ...
