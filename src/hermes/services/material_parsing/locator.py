"""Ordered material family localization rules."""

from __future__ import annotations

from dataclasses import dataclass
import re

from hermes.domain.materials import MaterialFamily

ACTIVITY_PREFIX = re.compile(r"^(?:INSTALACION|MONTAJE|RECORRIDO|ALINEACION)\b")


@dataclass(frozen=True, slots=True)
class FamilyLocation:
    """Family selected before any family-specific extraction."""

    family: MaterialFamily
    strong_rule: bool
    warnings: tuple[str, ...] = ()


def _looks_like_stud(text: str) -> bool:
    if not re.search(r"\bESPARRAGOS?\b", text):
        return False
    has_material_standard = "ASTM A193" in text
    has_diameter_and_length = bool(
        re.search(r'\d+(?:[ -]\d+/\d+|/\d+|\.\d+)?\s*"', text)
        and re.search(
            r'\bX\s+\d+(?:[ -]\d+/\d+|/\d+|\.\d+)?\s*"\s+DE\s+LONGITUD\b',
            text,
        )
    )
    return has_material_standard or has_diameter_and_length


def _looks_like_accessory_list(text: str) -> bool:
    accessory_terms = (
        "BRIDA",
        "CODO",
        "NIPLE",
        "COPLE",
        "TEE",
        "VALVULA",
    )
    present = sum(
        bool(re.search(rf"\b{term}\b", text)) for term in accessory_terms
    )
    return present >= 3


def classify_family(text: str) -> FamilyLocation:
    """Apply family rules in the mandatory precedence order."""
    if ACTIVITY_PREFIX.match(text):
        return FamilyLocation(
            MaterialFamily.UNKNOWN,
            strong_rule=False,
            warnings=("activity_description",),
        )

    if _looks_like_stud(text):
        return FamilyLocation(MaterialFamily.STUDS, strong_rule=True)

    if (
        re.match(r"^EMPAQUE\b", text)
        or re.match(r"^KIT\s+DE\s+JUNTA\s+AISLANTE\b", text)
        or (
            "TIPO VCS" in text
            and ("EMPAQUE" in text or "JUNTA AISLANTE" in text)
        )
    ) and "EMPAQUETADURA" not in text:
        return FamilyLocation(MaterialFamily.GASKETS, strong_rule=True)

    if re.match(r"^BRIDA\b", text) or re.match(
        r"^PREFABRICADO\b.*\bDE\s+BRIDA\b", text
    ):
        return FamilyLocation(MaterialFamily.FLANGES, strong_rule=True)

    if re.match(r"^CODO\b", text) and not _looks_like_accessory_list(text):
        return FamilyLocation(MaterialFamily.ELBOWS, strong_rule=True)
    if re.match(r"^CODO\b", text):
        return FamilyLocation(
            MaterialFamily.UNKNOWN,
            strong_rule=False,
            warnings=("accessory_list",),
        )

    if re.match(r"^TUBO\b", text) and not re.search(
        r"\b(?:PERFIL\s+TUBULAR|ESTRUCTURA\s+METALICA|SOPORTE)\b", text
    ):
        return FamilyLocation(MaterialFamily.PIPE, strong_rule=True)

    return FamilyLocation(
        MaterialFamily.UNKNOWN,
        strong_rule=False,
        warnings=("unknown_family",),
    )
