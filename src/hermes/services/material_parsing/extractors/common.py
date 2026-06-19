"""Small helpers shared by family-specific extractors."""

from __future__ import annotations

from typing import Any

from hermes.domain.materials import EvidenceSpan
from hermes.services.material_parsing.universal import ExtractedValue


def add_extracted(
    attributes: dict[str, Any],
    evidence: list[EvidenceSpan],
    field: str,
    extracted: ExtractedValue | None,
) -> None:
    """Add a parsed field and its evidence when present."""
    if extracted is None:
        return
    attributes[field] = extracted.value
    evidence.append(extracted.evidence)


def canonical_part(name: str, value: object | None) -> str:
    """Render one stable canonical key component."""
    if isinstance(value, bool):
        rendered = str(value).lower()
    else:
        rendered = "" if value is None else str(value)
    return f"{name}={rendered}"


def missing(required: tuple[str, ...], attributes: dict[str, Any]) -> tuple[str, ...]:
    """Return required fields whose normalized values are absent."""
    return tuple(
        field
        for field in required
        if field not in attributes or attributes[field] in {None, ""}
    )
