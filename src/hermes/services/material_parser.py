"""Public orchestration service for Hermes 0.4.0 material parsing."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pandas as pd

from hermes.domain.materials import MaterialFamily, ParsedMaterial
from hermes.services.material_parsing.extractors import EXTRACTORS
from hermes.services.material_parsing.locator import classify_family
from hermes.services.material_parsing.normalizer import normalize_text


class MaterialParser:
    """Normalize, locate, extract, validate, and key material descriptions."""

    material_column = "Data_DescripcionMaterial"
    item_column = "Data_DescripcionPartida"

    def parse_description(
        self,
        description: object,
        source_row: int = 0,
    ) -> ParsedMaterial:
        """Parse one description without performing inventory matching."""
        normalized = normalize_text(description)
        try:
            location = classify_family(normalized.text)
            if location.family is MaterialFamily.UNKNOWN:
                return self._unknown_result(
                    normalized.raw,
                    normalized.text,
                    source_row,
                    location.warnings,
                )

            extraction = EXTRACTORS[location.family].extract(normalized)
        except (ArithmeticError, TypeError, ValueError):
            return self._unknown_result(
                normalized.raw,
                normalized.text,
                source_row,
                ("parse_error",),
            )

        missing_warnings = tuple(
            f"missing_{field}" for field in extraction.missing_fields
        )
        warnings = list(location.warnings)
        warnings.extend(extraction.warnings)
        warnings.extend(missing_warnings)

        required_total = len(extraction.required_fields)
        present_required = required_total - len(extraction.missing_fields)
        required_score = (
            0.40 * present_required / required_total if required_total else 0.40
        )
        confidence = 0.25 if location.strong_rule else 0.0
        confidence += required_score
        if extraction.has_norm:
            confidence += 0.15
        if extraction.has_optional_context:
            confidence += 0.10
        confidence -= 0.15 * len(extraction.missing_fields)
        if "multiple_diameter_candidates" in extraction.warnings:
            confidence -= 0.10
        if "schedule_thickness_conflict" in extraction.warnings:
            confidence -= 0.10
        confidence = round(max(0.0, min(1.0, confidence)), 2)
        if confidence < 0.65:
            warnings.append("review_required")

        evidence = tuple(
            sorted(
                extraction.evidence,
                key=lambda item: (item.start, item.end, item.field),
            )
        )
        return ParsedMaterial(
            source_row=source_row,
            raw_description=normalized.raw,
            normalized_description=normalized.text,
            family=location.family,
            attributes=extraction.attributes,
            canonical_key=extraction.canonical_key,
            confidence_score=confidence,
            warnings=self._ordered_warnings(tuple(warnings)),
            evidence_spans=evidence,
        )

    @classmethod
    def _unknown_result(
        cls,
        raw_description: str,
        normalized_description: str,
        source_row: int,
        warnings: tuple[str, ...],
    ) -> ParsedMaterial:
        return ParsedMaterial(
            source_row=source_row,
            raw_description=raw_description,
            normalized_description=normalized_description,
            family=MaterialFamily.UNKNOWN,
            attributes={},
            canonical_key="",
            confidence_score=0.0,
            warnings=cls._ordered_warnings((*warnings, "review_required")),
            evidence_spans=(),
        )

    def parse_row(
        self,
        source_row: int,
        material_description: object,
        item_description: object = None,
    ) -> ParsedMaterial:
        """Parse a row, using the item description only as controlled fallback."""
        primary = self._cell_text(material_description)
        secondary = self._cell_text(item_description)

        if not primary:
            parsed = self.parse_description(secondary, source_row)
            if secondary:
                return self._with_warning(
                    parsed,
                    "used_secondary_description",
                )
            return parsed

        parsed_primary = self.parse_description(primary, source_row)
        if not secondary or not self._needs_fallback(parsed_primary):
            return parsed_primary
        if "activity_description" in parsed_primary.warnings:
            return parsed_primary

        if parsed_primary.family is MaterialFamily.UNKNOWN:
            parsed_secondary = self.parse_description(secondary, source_row)
            if parsed_secondary.family is not MaterialFamily.UNKNOWN:
                return self._with_warning(
                    parsed_secondary,
                    "used_secondary_description",
                )
            return parsed_primary

        combined = f"{primary} {secondary}".strip()
        parsed_combined = self.parse_description(combined, source_row)
        if (
            parsed_combined.family is parsed_primary.family
            and self._missing_count(parsed_combined)
            < self._missing_count(parsed_primary)
        ):
            return self._with_warning(
                parsed_combined,
                "used_secondary_description",
            )
        return parsed_primary

    def parse_dataframe(
        self,
        dataframe: pd.DataFrame,
        material_column: str = material_column,
        item_column: str = item_column,
        first_source_row: int = 2,
    ) -> list[ParsedMaterial]:
        """Parse every row using the catalog columns defined by the spec."""
        if material_column not in dataframe.columns:
            raise ValueError(
                f"Missing required material description column: {material_column}"
            )
        has_item_column = item_column in dataframe.columns
        results = []
        for offset, (_, row) in enumerate(dataframe.iterrows()):
            results.append(
                self.parse_row(
                    source_row=first_source_row + offset,
                    material_description=row[material_column],
                    item_description=row[item_column] if has_item_column else None,
                )
            )
        return results

    @staticmethod
    def _cell_text(value: Any) -> str:
        if value is None:
            return ""
        try:
            if bool(pd.isna(value)):
                return ""
        except (TypeError, ValueError):
            pass
        return str(value).strip()

    @staticmethod
    def _needs_fallback(parsed: ParsedMaterial) -> bool:
        return parsed.family is MaterialFamily.UNKNOWN or any(
            warning.startswith("missing_") for warning in parsed.warnings
        )

    @staticmethod
    def _missing_count(parsed: ParsedMaterial) -> int:
        return sum(
            warning.startswith("missing_") for warning in parsed.warnings
        )

    @classmethod
    def _with_warning(
        cls,
        parsed: ParsedMaterial,
        warning: str,
    ) -> ParsedMaterial:
        return replace(
            parsed,
            warnings=cls._ordered_warnings((*parsed.warnings, warning)),
        )

    @staticmethod
    def _ordered_warnings(warnings: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(warnings))
