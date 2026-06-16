"""Structured material parsing results used before inventory matching."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class MaterialFamily(str, Enum):
    """Material families recognized by Hermes 0.4.0."""

    STUDS = "ESPARRAGOS"
    GASKETS = "EMPAQUES"
    PIPE = "TUBERIA"
    FLANGES = "BRIDAS"
    ELBOWS = "CODOS"
    VALVES = "VALVULAS"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """Location in the untouched source text that supports one attribute."""

    field: str
    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, str | int]:
        """Return the JSON-compatible representation required by Hermes."""
        return {
            "field": self.field,
            "text": self.text,
            "start": self.start,
            "end": self.end,
        }


@dataclass(frozen=True, slots=True)
class ParsedMaterial:
    """Normalized technical description produced before inventory matching."""

    source_row: int
    raw_description: str
    normalized_description: str
    family: MaterialFamily
    attributes: dict[str, Any]
    canonical_key: str
    confidence_score: float
    warnings: tuple[str, ...] = ()
    evidence_spans: tuple[EvidenceSpan, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Return the minimum row output defined for Hermes 0.4.0."""
        return {
            "source_row": self.source_row,
            "raw_description": self.raw_description,
            "normalized_description": self.normalized_description,
            "family": self.family.value,
            "attributes": dict(self.attributes),
            "canonical_key": self.canonical_key,
            "confidence_score": self.confidence_score,
            "warnings": list(self.warnings),
            "evidence_spans": [
                evidence.to_dict() for evidence in self.evidence_spans
            ],
        }
