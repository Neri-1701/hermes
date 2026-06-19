"""Extractor for inventory pipe descriptions."""

from __future__ import annotations

import re

from hermes.services.material_parsing.extractors.base import FamilyExtraction
from hermes.services.material_parsing.extractors.common import (
    add_extracted,
    canonical_part,
)
from hermes.services.material_parsing.normalizer import NormalizedText
from hermes.services.material_parsing.thickness_resolver import (
    add_resolved_thickness,
)
from hermes.services.material_parsing.universal import (
    ExtractedValue,
    extract_astm_specifications,
    extract_compliance_standards,
    extract_diameter,
    extract_material_base,
    extract_schedule,
    extract_thickness,
    format_decimal_inches,
    format_inches,
)


def _choice(
    normalized: NormalizedText,
    field: str,
    choices: tuple[tuple[str, str], ...],
) -> ExtractedValue | None:
    for value, pattern in choices:
        match = re.search(pattern, normalized.text)
        if match is not None:
            return ExtractedValue(
                value=value,
                evidence=normalized.evidence(field, *match.span()),
                normalized_start=match.start(),
                normalized_end=match.end(),
            )
    return None


class PipeExtractor:
    """Extract dimensions, construction, material, and standards for pipe."""

    def extract(self, normalized: NormalizedText) -> FamilyExtraction:
        attributes: dict[str, object] = {}
        evidence = []
        warnings: list[str] = []

        diameter_result = extract_diameter(
            normalized,
            family_terms=("TUBO",),
            minimum=0.5,
            maximum=60,
        )
        add_extracted(attributes, evidence, "diametro", diameter_result.extracted)
        if diameter_result.conflicting_candidates:
            warnings.append("multiple_diameter_candidates")

        material = extract_material_base(normalized)
        add_extracted(attributes, evidence, "material_base", material)
        schedule = extract_schedule(normalized)
        if schedule is not None:
            if schedule.number is not None:
                attributes["cedula_num"] = schedule.number
            if schedule.alias is not None:
                attributes["cedula_alias"] = schedule.alias
            evidence.append(schedule.evidence)

        thickness = extract_thickness(normalized)
        add_extracted(attributes, evidence, "espesor", thickness)
        fabrication = _choice(
            normalized,
            "fabricacion",
            (
                ("SIN COSTURA", r"\bSIN\s+COSTURA\b"),
                ("CON COSTURA", r"\bCON\s+COSTURA\b"),
            ),
        )
        add_extracted(attributes, evidence, "fabricacion", fabrication)
        ends = _choice(
            normalized,
            "extremos",
            (
                ("PLANOS", r"\bEXTREMOS\s+PLANOS\b"),
                ("BISELADOS", r"\bEXTREMOS\s+BISELADOS\b"),
                ("ROSCADOS", r"\bEXTREMOS\s+ROSCADOS\b"),
            ),
        )
        add_extracted(attributes, evidence, "extremos", ends)

        specifications = extract_astm_specifications(normalized)
        if specifications:
            attributes["especificacion_material"] = specifications[0].value
            evidence.extend(item.evidence for item in specifications)
        standards = extract_compliance_standards(normalized)
        if standards:
            attributes["normas_cumplimiento"] = [item.value for item in standards]
            evidence.extend(item.evidence for item in standards)

        has_size_basis = schedule is not None or thickness is not None
        required = ("diametro", "material_base", "cedula_o_espesor")
        missing_fields = tuple(
            field
            for field, present in (
                ("diametro", "diametro" in attributes),
                ("material_base", "material_base" in attributes),
                ("cedula_o_espesor", has_size_basis),
            )
            if not present
        )
        add_resolved_thickness(attributes, warnings)

        diameter_key = (
            format_inches(attributes["diametro"], 8)
            if "diametro" in attributes
            else None
        )
        thickness_key = (
            format_decimal_inches(attributes["espesor_pared_in"])
            if "espesor_pared_in" in attributes
            else None
        )
        canonical_key = "|".join(
            (
                "TUBO",
                canonical_part("diametro", diameter_key),
                canonical_part("espesor_pared", thickness_key),
                canonical_part("material", attributes.get("material_base")),
                canonical_part("astm", attributes.get("especificacion_material")),
            )
        )
        return FamilyExtraction(
            attributes=attributes,
            canonical_key=canonical_key,
            required_fields=required,
            missing_fields=missing_fields,
            warnings=tuple(warnings),
            evidence=tuple(evidence),
            has_norm=bool(specifications or standards),
            has_optional_context=bool(fabrication or ends),
        )
