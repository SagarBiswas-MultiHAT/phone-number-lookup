"""Owner intelligence helpers for phoneint."""

from __future__ import annotations

from .classify import OwnershipType, classify
from .interface import (
    LegalBasis,
    OwnerAdapter,
    OwnerAdapterResult,
    OwnerAssociation,
    OwnerAuditRecord,
    OwnerIntelResult,
    OwnerPII,
    OwnershipType,
    now_utc,
)
from .signals import (
    OwnerIntelEngine,
    associations_from_evidence,
    extract_owner_signals,
    score_owner_confidence,
)
from .truecaller_adapter import TruecallerAdapter

__all__ = [
    "OwnershipType",
    "classify",
    "LegalBasis",
    "OwnerAdapter",
    "OwnerAdapterResult",
    "OwnerAssociation",
    "OwnerAuditRecord",
    "OwnerIntelResult",
    "OwnerPII",
    "now_utc",
    "OwnerIntelEngine",
    "associations_from_evidence",
    "extract_owner_signals",
    "score_owner_confidence",
    "TruecallerAdapter",
]
