"""Extractor for spiral-wound, insulating, and RTJ ring gaskets."""

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
    ExtractedValue,
    extract_class,
    extract_compliance_standards,
    extract_diameter,
    extract_face,
    extract_material_base,
    format_inches,
)


def _from_match(
    normalized: NormalizedText,
    field: str,
    value: object,
    match: re.Match[str],
) -> ExtractedValue:
    return ExtractedValue(
        value=value,
        evidence=normalized.evidence(field, *match.span()),
        normalized_start=match.start(),
        normalized_end=match.end(),
    )


def _extract_type(normalized: NormalizedText) -> ExtractedValue | None:
    choices = (
        ("ESPIROMETALICO", re.compile(r"\bESPIROMETALICO\b")),
        (
            "VCS",
            re.compile(r"\b(?:TIPO\s+VCS|KIT\s+DE\s+JUNTA\s+AISLANTE|JUNTA\s+AISLANTE)\b"),
        ),
        (
            "ANILLO",
            re.compile(r"\b(?:TIPO\s+ANILLO|ANILLO\s+OCTAGONAL|RTJ)\b"),
        ),
    )
    for value, pattern in choices:
        match = pattern.search(normalized.text)
        if match is not None:
            return _from_match(normalized, "tipo", value, match)
    return None


class GasketExtractor:
    """Run a subtype-aware parser for each recognized gasket construction."""

    def extract(self, normalized: NormalizedText) -> FamilyExtraction:
        attributes: dict[str, object] = {}
        evidence = []
        warnings: list[str] = []

        gasket_type = _extract_type(normalized)
        add_extracted(attributes, evidence, "tipo", gasket_type)
        diameter_result = extract_diameter(
            normalized,
            family_terms=("EMPAQUE", "JUNTA AISLANTE"),
            minimum=0.5,
            maximum=60,
        )
        add_extracted(attributes, evidence, "diametro", diameter_result.extracted)
        if diameter_result.conflicting_candidates:
            warnings.append("multiple_diameter_candidates")

        pressure_class = extract_class(normalized)
        add_extracted(attributes, evidence, "clase", pressure_class)
        face = extract_face(normalized)
        add_extracted(attributes, evidence, "cara", face)

        subtype = attributes.get("tipo")
        if subtype == "ESPIROMETALICO":
            for field, phrase in (
                ("anillo_centrador", r"\bANILLO\s+CENTRADOR\b"),
                ("anillo_interior", r"\bANILLO\s+INTERIOR\b"),
            ):
                match = re.search(phrase, normalized.text)
                attributes[field] = match is not None
                if match is not None:
                    evidence.append(normalized.evidence(field, *match.span()))

        ring_number = re.search(r"\bR-\d+\b", normalized.text)
        if subtype == "ANILLO" and ring_number is not None:
            add_extracted(
                attributes,
                evidence,
                "numero_anillo",
                _from_match(
                    normalized,
                    "numero_anillo",
                    ring_number.group(0),
                    ring_number,
                ),
            )

        material = extract_material_base(normalized)
        add_extracted(attributes, evidence, "material_base", material)
        standards = extract_compliance_standards(normalized)
        if standards:
            attributes["normas_cumplimiento"] = [item.value for item in standards]
            evidence.extend(item.evidence for item in standards)

        if subtype in {"ESPIROMETALICO", "VCS"}:
            required = ("tipo", "diametro", "clase")
        elif subtype == "ANILLO":
            required = ("tipo", "numero_anillo")
        else:
            required = ("tipo", "diametro")
        missing_fields = missing(required, attributes)

        diameter_key = (
            format_inches(attributes["diametro"], 8)
            if "diametro" in attributes
            else None
        )
        if subtype == "ESPIROMETALICO":
            parts = (
                "EMPAQUE",
                canonical_part("tipo", subtype),
                canonical_part("diametro", diameter_key),
                canonical_part("clase", attributes.get("clase")),
                canonical_part("centrador", attributes.get("anillo_centrador")),
                canonical_part("interior", attributes.get("anillo_interior")),
                canonical_part("cara", attributes.get("cara")),
            )
        elif subtype == "VCS":
            parts = (
                "EMPAQUE",
                canonical_part("tipo", subtype),
                canonical_part("diametro", diameter_key),
                canonical_part("clase", attributes.get("clase")),
                canonical_part("cara", attributes.get("cara")),
                canonical_part("sistema", "VCS"),
            )
        else:
            asme_b1620 = next(
                (
                    item.value
                    for item in standards
                    if item.value == "ASME B16.20"
                ),
                None,
            )
            parts = (
                "EMPAQUE",
                canonical_part("tipo", subtype),
                canonical_part("numero_anillo", attributes.get("numero_anillo")),
                canonical_part("material", attributes.get("material_base")),
                canonical_part("norma", asme_b1620),
            )

        return FamilyExtraction(
            attributes=attributes,
            canonical_key="|".join(parts),
            required_fields=required,
            missing_fields=missing_fields,
            warnings=tuple(warnings),
            evidence=tuple(evidence),
            has_norm=bool(standards),
            has_optional_context=bool(
                face
                or attributes.get("anillo_centrador")
                or attributes.get("anillo_interior")
                or material
            ),
        )
