"""Universal dimensional and technical attribute parsers."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
import re
from typing import Any

from hermes.domain.materials import EvidenceSpan
from hermes.services.material_parsing.normalizer import NormalizedText

NUM_PATTERN = (
    r"(?:\d+\s*-\s*\d+/\d+|\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
)

CLASS_VALUES = "150|300|400|600|800|900|1500|2500|3000|6000"
CLASS_PATTERN = re.compile(
    rf"\b(?:CLASE|CLASS)\s*:?\s*(?P<label>{CLASS_VALUES})\b"
    rf"|\b(?P<pounds>{CLASS_VALUES})\s*(?:LIBRAS|LB)\b"
)
COMPOSITE_SCHEDULE_PATTERN = re.compile(
    r"\bCEDULA\s*\((?P<alias>[^,\)]*?)\s*,\s*0*(?P<num>[0-9]+)\)"
)
SIMPLE_SCHEDULE_PATTERN = re.compile(
    r"\b(?:CEDULA|SCHEDULE|SCH)\s*:?\s*"
    r"(?P<value>0*[0-9]+S?|STD|XS|XXS)\b"
)
THICKNESS_PATTERN = re.compile(
    rf"(?:\bDE\s+|\bCON\s+ESPESOR\s+DE\s+)?"
    rf"(?P<value>{NUM_PATTERN})\s*\"\s*(?:DE\s+)?ESPESOR\b"
)
PREFIX_THICKNESS_PATTERN = re.compile(
    rf"\bESPESOR\s+DE\s+(?P<value>{NUM_PATTERN})\s*\""
)

MATERIAL_PATTERNS = (
    ("ACERO INOXIDABLE", re.compile(r"\bACERO\s+INOXIDABLE\b")),
    ("ACERO AL CARBONO", re.compile(r"\bACERO\s+AL\s+CARBONO\b")),
    ("ALEACION DE ACERO", re.compile(r"\bALEACION\s+DE\s+ACERO\b")),
    ("BRONCE", re.compile(r"\bBRONCE\b")),
    ("COBRE", re.compile(r"\bCOBRE\b")),
)
ASTM_PATTERN = re.compile(
    r"\bASTM\s+[A-Z]\d+(?:/[A-Z]\d+[A-Z]?)?"
    r"(?:\s+GRADO\s+[A-Z0-9-]+)?\b"
)
COMPLIANCE_PATTERNS = (
    re.compile(r"\bASME\s+B\d+(?:\.\d+)+\b"),
    re.compile(r"\bANSI/NACE\s+MR\d+(?:/ISO\s+\d+(?:-\d+)?)?\b"),
    re.compile(r"\bNACE(?:/ISO)?\s+[A-Z0-9./-]+\b"),
    re.compile(r"\bISO\s+\d+(?:-\d+)?\b"),
    re.compile(r"\bAPI\s+[A-Z0-9./-]+\b"),
)

@dataclass(frozen=True, slots=True)
class ExtractedValue:
    """One parsed value and the raw evidence that produced it."""

    value: Any
    evidence: EvidenceSpan
    normalized_start: int
    normalized_end: int


@dataclass(frozen=True, slots=True)
class DiameterResult:
    """Selected diameter plus ambiguity information."""

    extracted: ExtractedValue | None
    conflicting_candidates: bool = False


@dataclass(frozen=True, slots=True)
class ScheduleResult:
    """Normalized schedule number/alias and its evidence."""

    number: int | None
    alias: str | None
    evidence: EvidenceSpan


def parse_inch_number(value: str) -> float:
    """Convert decimal, fractional, and mixed imperial text to a float."""
    cleaned = value.strip().replace('"', "")
    mixed_hyphen = re.fullmatch(r"(\d+)\s*-\s*(\d+)/(\d+)", cleaned)
    mixed_space = re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", cleaned)
    fraction = re.fullmatch(r"(\d+)/(\d+)", cleaned)

    if mixed_hyphen:
        whole, numerator, denominator = map(int, mixed_hyphen.groups())
        return float(whole + Fraction(numerator, denominator))
    if mixed_space:
        whole, numerator, denominator = map(int, mixed_space.groups())
        return float(whole + Fraction(numerator, denominator))
    if fraction:
        numerator, denominator = map(int, fraction.groups())
        return float(Fraction(numerator, denominator))
    return float(cleaned)


def format_inches(value: float, max_denominator: int = 16) -> str:
    """Return a readable imperial representation without rounding decimals."""
    nearest = Fraction(value).limit_denominator(max_denominator)
    if math.isclose(float(nearest), value, abs_tol=1e-8):
        whole, numerator = divmod(nearest.numerator, nearest.denominator)
        if numerator == 0:
            return f'{whole}"'
        if whole:
            return f'{whole}-{numerator}/{nearest.denominator}"'
        return f'{numerator}/{nearest.denominator}"'
    return f'{value:g}"'


def format_decimal_inches(value: float) -> str:
    """Render decimal thickness with at least three decimal places."""
    rendered = f"{value:.6f}".rstrip("0")
    whole, decimal = rendered.split(".")
    rendered = f"{whole}.{decimal.ljust(3, '0')}"
    return f'{rendered}"'


def _extracted(
    normalized: NormalizedText,
    field: str,
    match: re.Match[str],
    group: str | int = 0,
    value: Any | None = None,
) -> ExtractedValue:
    start, end = match.span(group)
    parsed_value = match.group(group) if value is None else value
    return ExtractedValue(
        value=parsed_value,
        evidence=normalized.evidence(field, start, end),
        normalized_start=start,
        normalized_end=end,
    )


def extract_diameter(
    normalized: NormalizedText,
    family_terms: tuple[str, ...],
    minimum: float,
    maximum: float,
) -> DiameterResult:
    """Extract diameter by explicit context first, then quoted fallback."""
    patterns = (
        re.compile(
            rf"\bDE\s+(?P<num>{NUM_PATTERN})\s*\"?\s*"
            rf"(?:\([^)]*MM\)\s*)?DE\s+DIAMETRO\s+NOMINAL\b"
        ),
        re.compile(
            rf"(?P<num>{NUM_PATTERN})\s*\"?\s*"
            rf"(?:DE\s+)?(?:DIAMETRO|DIA|DIAM)\b"
        ),
        re.compile(
            rf"\b(?:DIAMETRO|DIA|DIAM)(?:\s+NOMINAL)?\s*(?:DE\s+)?"
            rf"(?P<num>{NUM_PATTERN})\s*\"(?!\s*MM\b)"
        ),
    )

    candidates: list[tuple[int, int, float, re.Match[str]]] = []
    for priority, pattern in enumerate(patterns):
        for match in pattern.finditer(normalized.text):
            value = parse_inch_number(match.group("num"))
            if minimum <= value <= maximum:
                candidates.append((priority, match.start("num"), value, match))

    if not candidates:
        quoted_pattern = re.compile(rf"(?P<num>{NUM_PATTERN})\s*\"")
        family_position = min(
            (
                normalized.text.find(term)
                for term in family_terms
                if term in normalized.text
            ),
            default=-1,
        )
        for match in quoted_pattern.finditer(normalized.text):
            value = parse_inch_number(match.group("num"))
            suffix = normalized.text[match.end() : match.end() + 18]
            if not minimum <= value <= maximum:
                continue
            if re.match(r"\s*(?:MM\b|DE\s+ESPESOR\b|DE\s+LONGITUD\b)", suffix):
                continue
            if family_position >= 0 and abs(match.start() - family_position) <= 140:
                candidates.append((3, match.start("num"), value, match))

    if not candidates:
        return DiameterResult(None)

    candidates.sort(key=lambda candidate: (candidate[0], candidate[1]))
    _, _, selected_value, selected_match = candidates[0]
    unique_values = {round(candidate[2], 8) for candidate in candidates}
    return DiameterResult(
        extracted=_extracted(
            normalized,
            "diametro",
            selected_match,
            "num",
            selected_value,
        ),
        conflicting_candidates=len(unique_values) > 1,
    )


def extract_class(normalized: NormalizedText) -> ExtractedValue | None:
    """Extract a pressure class in label or pounds notation."""
    match = CLASS_PATTERN.search(normalized.text)
    if match is None:
        return None
    group = "label" if match.group("label") else "pounds"
    return _extracted(
        normalized,
        "clase",
        match,
        group,
        int(match.group(group)),
    )


def extract_schedule(normalized: NormalizedText) -> ScheduleResult | None:
    """Extract simple or composite schedule notation."""
    composite = COMPOSITE_SCHEDULE_PATTERN.search(normalized.text)
    if composite is not None:
        alias = composite.group("alias").strip().upper() or None
        return ScheduleResult(
            number=int(composite.group("num")),
            alias=alias,
            evidence=normalized.evidence("cedula", *composite.span()),
        )

    simple = SIMPLE_SCHEDULE_PATTERN.search(normalized.text)
    if simple is None:
        return None
    value = simple.group("value").upper()
    return ScheduleResult(
        number=int(value) if value.isdigit() else None,
        alias=None if value.isdigit() else value,
        evidence=normalized.evidence("cedula", *simple.span()),
    )


def extract_thickness(normalized: NormalizedText) -> ExtractedValue | None:
    """Extract wall or plate thickness expressed in inches."""
    match = THICKNESS_PATTERN.search(normalized.text)
    if match is None:
        match = PREFIX_THICKNESS_PATTERN.search(normalized.text)
    if match is None:
        return None
    return _extracted(
        normalized,
        "espesor",
        match,
        "value",
        parse_inch_number(match.group("value")),
    )


def extract_material_base(normalized: NormalizedText) -> ExtractedValue | None:
    """Extract a normalized base material independently from ASTM data."""
    for value, pattern in MATERIAL_PATTERNS:
        match = pattern.search(normalized.text)
        if match is not None:
            return _extracted(normalized, "material_base", match, value=value)
    return None


def extract_astm_specifications(
    normalized: NormalizedText,
) -> tuple[ExtractedValue, ...]:
    """Extract material specifications without mixing compliance standards."""
    return tuple(
        _extracted(
            normalized,
            "especificacion_material",
            match,
            value=match.group(0),
        )
        for match in ASTM_PATTERN.finditer(normalized.text)
    )


def extract_compliance_standards(
    normalized: NormalizedText,
) -> tuple[ExtractedValue, ...]:
    """Extract unique ASME, API, NACE, and ISO compliance standards."""
    extracted: list[ExtractedValue] = []
    seen: set[tuple[int, int]] = set()
    for pattern in COMPLIANCE_PATTERNS:
        for match in pattern.finditer(normalized.text):
            if match.span() in seen:
                continue
            seen.add(match.span())
            extracted.append(
                _extracted(
                    normalized,
                    "norma_cumplimiento",
                    match,
                    value=match.group(0),
                )
            )
    return tuple(sorted(extracted, key=lambda item: item.evidence.start))


def extract_face(normalized: NormalizedText) -> ExtractedValue | None:
    """Extract RF, RTJ, or FF facing notation."""
    patterns = (
        ("RF", re.compile(r"\bCARA\s+REALZADA\b|\(\s*-?RF\s*\)")),
        ("RTJ", re.compile(r"\bJUNTA\s+DE\s+ANILLO\b|\(\s*-?RTJ\s*\)")),
        ("FF", re.compile(r"\bCARA\s+PLANA\b|\(\s*-?FF\s*\)")),
    )
    for value, pattern in patterns:
        match = pattern.search(normalized.text)
        if match is not None:
            return _extracted(normalized, "cara", match, value=value)
    return None


def validate_increment(value: float, increment: float) -> bool:
    """Return whether a dimension aligns with its family increment."""
    quotient = value / increment
    return math.isclose(quotient, round(quotient), abs_tol=1e-8)
