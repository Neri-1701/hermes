"""Extractor for industrial flanges."""

from __future__ import annotations

import re

from hermes.services.material_parsing.extractors.base import FamilyExtraction
from hermes.services.material_parsing.extractors.common import (
    add_extracted,
    canonical_part,
)
from hermes.services.material_parsing.normalizer import NormalizedText
from hermes.services.material_parsing.universal import (
    ExtractedValue,
    extract_astm_specifications,
    extract_class,
    extract_compliance_standards,
    extract_diameter,
    extract_face,
    extract_material_base,
    extract_schedule,
    extract_thickness,
    format_inches,
    schedule_thickness_conflict,
)

FLANGE_TYPES = (
    ("WN", r"\(\s*-?WN\s*\)|\bCUELLO\s+SOLDABLE\b"),
    ("BL", r"\(\s*-?BL\s*\)|\b(?:BRIDA\s+)?CIEGA\b"),
    ("SO", r"\(\s*-?SO\s*\)|\bDESLIZABLE\b"),
    ("THD", r"\(\s*-?THD\s*\)|\bROSCADA\b"),
    ("SW", r"\(\s*-?SW\s*\)|\bSOCKET\s+WELD\b|\bINSERTO\s+SOLDABLE\b"),
    ("LAP JOINT", r"\bLAP\s+JOINT\b"),
)


def _extract_type(normalized: NormalizedText) -> ExtractedValue | None:
    for value, pattern in FLANGE_TYPES:
        match = re.search(pattern, normalized.text)
        if match is not None:
            return ExtractedValue(
                value=value,
                evidence=normalized.evidence("tipo_brida", *match.span()),
                normalized_start=match.start(),
                normalized_end=match.end(),
            )
    return None


class FlangeExtractor:
    """Extract flange type and only require schedule where it applies."""

    def extract(self, normalized: NormalizedText) -> FamilyExtraction:
        attributes: dict[str, object] = {}
        evidence = []
        warnings: list[str] = []

        flange_type = _extract_type(normalized)
        add_extracted(attributes, evidence, "tipo_brida", flange_type)
        diameter_result = extract_diameter(
            normalized,
            family_terms=("BRIDA",),
            minimum=0.5,
            maximum=60,
        )
        add_extracted(attributes, evidence, "diametro", diameter_result.extracted)
        if diameter_result.conflicting_candidates:
            warnings.append("multiple_diameter_candidates")

        pressure_class = extract_class(normalized)
        add_extracted(attributes, evidence, "clase", pressure_class)
        schedule = extract_schedule(normalized)
        if schedule is not None:
            if schedule.number is not None:
                attributes["cedula_num"] = schedule.number
            if schedule.alias is not None:
                attributes["cedula_alias"] = schedule.alias
            evidence.append(schedule.evidence)
        thickness = extract_thickness(normalized)
        add_extracted(attributes, evidence, "espesor", thickness)
        face = extract_face(normalized)
        add_extracted(attributes, evidence, "cara", face)
        material = extract_material_base(normalized)
        add_extracted(attributes, evidence, "material_base", material)

        specifications = extract_astm_specifications(normalized)
        if specifications:
            attributes["especificacion_material"] = specifications[0].value
            evidence.extend(item.evidence for item in specifications)
        standards = extract_compliance_standards(normalized)
        if standards:
            attributes["normas_cumplimiento"] = [item.value for item in standards]
            evidence.extend(item.evidence for item in standards)

        type_value = attributes.get("tipo_brida")
        schedule_applies = type_value == "WN"
        has_schedule_basis = schedule is not None or thickness is not None
        required = ("tipo_brida", "diametro", "clase", "material_base")
        if schedule_applies:
            required += ("cedula_o_espesor",)
        missing_fields = tuple(
            field
            for field, present in (
                ("tipo_brida", "tipo_brida" in attributes),
                ("diametro", "diametro" in attributes),
                ("clase", "clase" in attributes),
                ("material_base", "material_base" in attributes),
                (
                    "cedula_o_espesor",
                    not schedule_applies or has_schedule_basis,
                ),
            )
            if not present and (field != "cedula_o_espesor" or schedule_applies)
        )

        diameter_value = attributes.get("diametro")
        schedule_number = attributes.get("cedula_num")
        thickness_value = attributes.get("espesor")
        if schedule_thickness_conflict(
            diameter_value if isinstance(diameter_value, float) else None,
            schedule_number if isinstance(schedule_number, int) else None,
            thickness_value if isinstance(thickness_value, float) else None,
        ):
            warnings.append("schedule_thickness_conflict")

        diameter_key = (
            format_inches(attributes["diametro"], 8)
            if "diametro" in attributes
            else None
        )
        schedule_key = attributes.get("cedula_num") or attributes.get("cedula_alias")
        common_parts = (
            "BRIDA",
            canonical_part("tipo", type_value),
            canonical_part("diametro", diameter_key),
            canonical_part("clase", attributes.get("clase")),
        )
        if type_value == "WN":
            common_parts += (canonical_part("cedula", schedule_key),)
        common_parts += (
            canonical_part("cara", attributes.get("cara")),
            canonical_part("material", attributes.get("material_base")),
            canonical_part("astm", attributes.get("especificacion_material")),
        )
        return FamilyExtraction(
            attributes=attributes,
            canonical_key="|".join(common_parts),
            required_fields=required,
            missing_fields=missing_fields,
            warnings=tuple(warnings),
            evidence=tuple(evidence),
            has_norm=bool(specifications or standards),
            has_optional_context=bool(face or thickness),
        )
