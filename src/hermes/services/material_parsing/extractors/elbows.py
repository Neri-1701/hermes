"""Extractor for butt-weld and forged elbows."""

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
    extract_material_base,
    extract_schedule,
    extract_thickness,
    format_inches,
    schedule_thickness_conflict,
)


def _extract_choice(
    normalized: NormalizedText,
    field: str,
    choices: tuple[tuple[object, str], ...],
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


class ElbowExtractor:
    """Extract angle/radius and choose class or schedule by elbow type."""

    def extract(self, normalized: NormalizedText) -> FamilyExtraction:
        attributes: dict[str, object] = {}
        evidence = []
        warnings: list[str] = []

        angle = _extract_choice(
            normalized,
            "angulo",
            (
                (180, r"\b180\s+GRADOS\b"),
                (90, r"\b90\s+GRADOS\b"),
                (45, r"\b45\s+GRADOS\b"),
            ),
        )
        add_extracted(attributes, evidence, "angulo", angle)
        radius = _extract_choice(
            normalized,
            "radio",
            (
                ("LARGO", r"\bRADIO\s+LARGO\b"),
                ("CORTO", r"\bRADIO\s+CORTO\b"),
            ),
        )
        add_extracted(attributes, evidence, "radio", radius)
        diameter_result = extract_diameter(
            normalized,
            family_terms=("CODO",),
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
        ends = _extract_choice(
            normalized,
            "extremos",
            (
                ("SW", r"\b(?:EXTREMOS\s+)?INSERTO\s+SOLDABLE\b|\bSOCKET\s+WELD\b"),
                ("THD", r"\b(?:EXTREMOS\s+)?ROSCADOS?\b"),
                ("BW", r"\bEXTREMOS\s+BISELADOS\b|\bBUTT\s+WELD\b"),
            ),
        )
        add_extracted(attributes, evidence, "extremos", ends)
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

        if angle is not None:
            type_value = f"{angle.value} GRADOS"
            if radius is not None:
                type_value += f" RADIO {radius.value}"
            attributes["tipo_codo"] = type_value

        has_pressure_basis = pressure_class is not None or schedule is not None
        required = ("angulo", "diametro", "material_base", "clase_o_cedula")
        missing_fields = tuple(
            field
            for field, present in (
                ("angulo", "angulo" in attributes),
                ("diametro", "diametro" in attributes),
                ("material_base", "material_base" in attributes),
                ("clase_o_cedula", has_pressure_basis),
            )
            if not present
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
        is_butt_weld = schedule is not None or any(
            item.value == "ASME B16.9" for item in standards
        )
        if is_butt_weld:
            parts = (
                "CODO",
                canonical_part("angulo", attributes.get("angulo")),
                canonical_part("radio", attributes.get("radio")),
                canonical_part("diametro", diameter_key),
                canonical_part(
                    "cedula",
                    attributes.get("cedula_num") or attributes.get("cedula_alias"),
                ),
                canonical_part("material", attributes.get("material_base")),
                canonical_part("astm", attributes.get("especificacion_material")),
                canonical_part("norma", "ASME B16.9"),
            )
        else:
            parts = (
                "CODO",
                canonical_part("angulo", attributes.get("angulo")),
                canonical_part("diametro", diameter_key),
                canonical_part("clase", attributes.get("clase")),
                canonical_part("extremos", attributes.get("extremos")),
                canonical_part("material", attributes.get("material_base")),
                canonical_part("astm", attributes.get("especificacion_material")),
                canonical_part("norma", "ASME B16.11"),
            )
        return FamilyExtraction(
            attributes=attributes,
            canonical_key="|".join(parts),
            required_fields=required,
            missing_fields=missing_fields,
            warnings=tuple(warnings),
            evidence=tuple(evidence),
            has_norm=bool(specifications or standards),
            has_optional_context=bool(radius or ends or thickness),
        )
