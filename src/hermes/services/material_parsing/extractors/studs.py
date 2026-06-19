"""Extractor for threaded studs."""

from __future__ import annotations

import re

from hermes.services.material_parsing.extractors.base import FamilyExtraction
from hermes.services.material_parsing.extractors.common import (
    add_extracted,
    canonical_part,
    missing,
)
from hermes.services.material_parsing.normalizer import NormalizedText
from hermes.services.material_parsing.universal import (
    NUM_PATTERN,
    ExtractedValue,
    extract_astm_specifications,
    extract_diameter,
    format_inches,
    parse_inch_number,
    validate_increment,
)

STUD_GRADES = ("B7M", "B8M", "B8", "B7")


def _extract_length(
    normalized: NormalizedText,
    after_position: int,
) -> ExtractedValue | None:
    primary = re.compile(
        rf"\bX\s+(?P<num>{NUM_PATTERN})\s*\"\s+DE\s+LONGITUD\b"
    )
    match = primary.search(normalized.text, after_position)

    if match is None:
        quoted = re.compile(rf"(?P<num>{NUM_PATTERN})\s*\"")
        for candidate in quoted.finditer(normalized.text, after_position):
            value = parse_inch_number(candidate.group("num"))
            suffix = normalized.text[candidate.end() : candidate.end() + 24]
            if not 1 <= value <= 45:
                continue
            if re.match(
                r"\s*(?:MM\b|DE\s+DIAMETRO\b|DE\s+ESPESOR\b|CLASE\b)",
                suffix,
            ):
                continue
            match = candidate
            break

    if match is None:
        return None
    start, end = match.span("num")
    return ExtractedValue(
        value=parse_inch_number(match.group("num")),
        evidence=normalized.evidence("longitud", start, end),
        normalized_start=start,
        normalized_end=end,
    )


def _extract_grade(normalized: NormalizedText) -> ExtractedValue | None:
    for grade in STUD_GRADES:
        match = re.search(rf"\b{grade}\b", normalized.text)
        if match is not None:
            return ExtractedValue(
                value=grade,
                evidence=normalized.evidence("grado", *match.span()),
                normalized_start=match.start(),
                normalized_end=match.end(),
            )
    return None


class StudExtractor:
    """Extract diameter, subsequent length, grade, and distinct ASTM norms."""

    def extract(self, normalized: NormalizedText) -> FamilyExtraction:
        attributes: dict[str, object] = {}
        evidence = []
        warnings: list[str] = []

        diameter_result = extract_diameter(
            normalized,
            family_terms=("ESPARRAGO", "ESPARRAGOS"),
            minimum=0.25,
            maximum=4,
        )
        diameter = diameter_result.extracted
        add_extracted(attributes, evidence, "diametro", diameter)
        if diameter_result.conflicting_candidates:
            warnings.append("multiple_diameter_candidates")

        length = _extract_length(
            normalized,
            diameter.normalized_end if diameter is not None else len(normalized.text),
        )
        add_extracted(attributes, evidence, "longitud", length)

        grade = _extract_grade(normalized)
        add_extracted(attributes, evidence, "grado", grade)

        specifications = extract_astm_specifications(normalized)
        stud_norm = next(
            (item for item in specifications if "A193" in item.value),
            None,
        )
        nut_norm = next(
            (item for item in specifications if "A194" in item.value),
            None,
        )
        add_extracted(attributes, evidence, "norma_material", stud_norm)
        add_extracted(attributes, evidence, "norma_tuercas", nut_norm)

        if diameter is not None and not validate_increment(diameter.value, 0.125):
            warnings.append("diameter_nonstandard_increment")
        if length is not None and not validate_increment(length.value, 0.25):
            warnings.append("length_nonstandard_increment")

        required = ("diametro", "longitud", "grado")
        missing_fields = missing(required, attributes)
        diameter_key = (
            format_inches(attributes["diametro"], 8)
            if "diametro" in attributes
            else None
        )
        length_key = (
            format_inches(attributes["longitud"], 4)
            if "longitud" in attributes
            else None
        )
        canonical_key = "|".join(
            (
                "ESPARRAGO",
                canonical_part("diametro", diameter_key),
                canonical_part("longitud", length_key),
                canonical_part("grado", attributes.get("grado")),
            )
        )
        return FamilyExtraction(
            attributes=attributes,
            canonical_key=canonical_key,
            required_fields=required,
            missing_fields=missing_fields,
            warnings=tuple(warnings),
            evidence=tuple(evidence),
            has_norm=stud_norm is not None,
            has_optional_context=nut_norm is not None,
        )
