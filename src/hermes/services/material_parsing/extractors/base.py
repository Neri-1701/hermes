"""Shared extractor result contract, not family extraction logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from hermes.domain.materials import EvidenceSpan
from hermes.services.material_parsing.normalizer import NormalizedText


@dataclass(frozen=True, slots=True)
class FamilyExtraction:
    """Attributes and validation metadata produced by one family extractor."""

    attributes: dict[str, Any]
    canonical_key: str
    required_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    evidence: tuple[EvidenceSpan, ...]
    has_norm: bool
    has_optional_context: bool


class MaterialExtractor(Protocol):
    """Interface implemented independently by every material family."""

    def extract(self, normalized: NormalizedText) -> FamilyExtraction:
        """Extract and normalize attributes for the selected family."""
