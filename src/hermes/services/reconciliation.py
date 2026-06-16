"""Segment requirements and inventory, then allocate exact matches."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

import pandas as pd

from hermes.domain.materials import MaterialFamily, ParsedMaterial
from hermes.domain.models import DataSource, HermesState
from hermes.domain.reconciliation import (
    ReconciliationReport,
    ReconciliationStatus,
)
from hermes.services.material_parser import MaterialParser


class ReconciliationError(ValueError):
    """Raised when configured data cannot be reconciled safely."""


@dataclass
class _InventoryRecord:
    source_row: int
    code: str
    description: str
    quantity: float
    remaining: float
    parsed: ParsedMaterial

    @property
    def allocated(self) -> float:
        return self.quantity - self.remaining


@dataclass(frozen=True, slots=True)
class _FieldRule:
    name: str
    weight: float
    anchor: bool = False


@dataclass(frozen=True, slots=True)
class _Candidate:
    record: _InventoryRecord
    score: float
    exact: bool


class ReconciliationService:
    """Run end-to-end material segmentation and inventory allocation."""

    def __init__(self, parser: MaterialParser | None = None) -> None:
        self._parser = parser or MaterialParser()

    def reconcile(self, state: HermesState) -> ReconciliationReport:
        """Process configured datasets and return all result tables."""
        inventory_dataset = state.dataset_for(DataSource.INVENTORY)
        requirements_dataset = state.dataset_for(DataSource.REQUIREMENTS)
        if inventory_dataset is None or requirements_dataset is None:
            raise ReconciliationError(
                "Carga los archivos de inventario y requerimientos antes de procesar."
            )

        inventory = self._build_inventory_records(
            inventory_dataset.dataframe,
            state.mappings,
        )
        requirements = self._build_requirement_records(
            requirements_dataset.dataframe,
            state.mappings,
        )
        inventory_by_family: dict[MaterialFamily, list[_InventoryRecord]] = {}
        for record in inventory:
            inventory_by_family.setdefault(record.parsed.family, []).append(
                record
            )

        match_rows = [
            self._match_requirement(
                requirement,
                inventory_by_family.get(
                    requirement["parsed"].family,
                    [],
                ),
            )
            for requirement in requirements
        ]
        return ReconciliationReport(
            matches=pd.DataFrame(match_rows),
            requirements=pd.DataFrame(
                self._requirement_segmentation_row(requirement)
                for requirement in requirements
            ),
            inventory=pd.DataFrame(
                self._inventory_segmentation_row(record)
                for record in inventory
            ),
        )

    def search_inventory(
        self,
        state: HermesState,
        query: object,
    ) -> pd.DataFrame:
        """Search loaded inventory with the canonical reconciliation rules."""
        inventory_dataset = state.dataset_for(DataSource.INVENTORY)
        if inventory_dataset is None:
            raise ReconciliationError(
                "Carga el archivo de inventario antes de buscar."
            )

        query_text = self._text(query)
        if not query_text:
            raise ReconciliationError(
                "Escribe una descripcion de material para buscar."
            )

        parsed_query = self._parser.parse_description(query_text)
        if parsed_query.family is MaterialFamily.UNKNOWN:
            return self._empty_search_results()

        inventory = self._build_inventory_records(
            inventory_dataset.dataframe,
            state.mappings,
        )
        results = []
        for record in inventory:
            candidate = self._candidate(parsed_query, record)
            if candidate is None:
                continue
            results.append(
                {
                    "tipo_coincidencia": (
                        "EXACTA" if candidate.exact else "PARCIAL"
                    ),
                    "score_coincidencia": round(candidate.score, 2),
                    "fila_inventario": record.source_row,
                    "codigo": record.code,
                    "descripcion": record.description,
                    "familia": record.parsed.family.value,
                    "cantidad_disponible": record.quantity,
                    "canonical_key_busqueda": parsed_query.canonical_key,
                    "canonical_key_inventario": record.parsed.canonical_key,
                    "warnings_busqueda": ", ".join(parsed_query.warnings),
                    "warnings_inventario": ", ".join(
                        record.parsed.warnings
                    ),
                }
            )

        if not results:
            return self._empty_search_results()
        return (
            pd.DataFrame(results)
            .sort_values(
                by=[
                    "tipo_coincidencia",
                    "score_coincidencia",
                    "cantidad_disponible",
                    "fila_inventario",
                ],
                ascending=[True, False, False, True],
            )
            .reset_index(drop=True)
        )

    def _build_inventory_records(
        self,
        dataframe: pd.DataFrame,
        mappings: dict[str, str],
    ) -> list[_InventoryRecord]:
        description_column = self._required_mapping(
            mappings,
            "inventory_description",
        )
        code_column = self._required_mapping(mappings, "inventory_code")
        quantity_column = self._required_mapping(
            mappings,
            "inventory_quantity",
        )

        records = []
        for offset, (_, row) in enumerate(dataframe.iterrows()):
            source_row = offset + 2
            code = self._text(row[code_column])
            if not code:
                continue
            description = self._text(row[description_column])
            quantity = self._quantity(
                row[quantity_column],
            )
            records.append(
                _InventoryRecord(
                    source_row=source_row,
                    code=code,
                    description=description,
                    quantity=quantity,
                    remaining=quantity,
                    parsed=self._parser.parse_description(
                        description,
                        source_row=source_row,
                    ),
                )
            )
        return records

    @staticmethod
    def _empty_search_results() -> pd.DataFrame:
        return pd.DataFrame(
            columns=[
                "tipo_coincidencia",
                "score_coincidencia",
                "fila_inventario",
                "codigo",
                "descripcion",
                "familia",
                "cantidad_disponible",
                "canonical_key_busqueda",
                "canonical_key_inventario",
                "warnings_busqueda",
                "warnings_inventario",
            ]
        )

    def _build_requirement_records(
        self,
        dataframe: pd.DataFrame,
        mappings: dict[str, str],
    ) -> list[dict[str, Any]]:
        description_column = self._required_mapping(
            mappings,
            "requirements_description",
        )
        quantity_column = self._required_mapping(
            mappings,
            "requirements_quantity",
        )
        udc_column = self._required_mapping(mappings, "requirements_udc")
        date_column = self._required_mapping(mappings, "requirements_date")
        secondary_column = mappings.get("requirements_item_description")
        if (
            not secondary_column
            and MaterialParser.item_column in dataframe.columns
            and MaterialParser.item_column != description_column
        ):
            secondary_column = MaterialParser.item_column

        records = []
        for offset, (_, row) in enumerate(dataframe.iterrows()):
            source_row = offset + 2
            primary = self._text(row[description_column])
            secondary = (
                self._text(row[secondary_column])
                if secondary_column and secondary_column in dataframe.columns
                else ""
            )
            records.append(
                {
                    "source_row": source_row,
                    "udc": self._text(row[udc_column]),
                    "date": self._text(row[date_column]),
                    "description": primary,
                    "secondary_description": secondary,
                    "quantity": self._quantity(
                        row[quantity_column],
                    ),
                    "parsed": self._parser.parse_row(
                        source_row=source_row,
                        material_description=primary,
                        item_description=secondary,
                    ),
                }
            )
        return records

    def _match_requirement(
        self,
        requirement: dict[str, Any],
        inventory: list[_InventoryRecord],
    ) -> dict[str, Any]:
        parsed: ParsedMaterial = requirement["parsed"]
        requested = requirement["quantity"]
        base = {
            "fila_requerimiento": requirement["source_row"],
            "udc": requirement["udc"],
            "fecha_programa": requirement["date"],
            "descripcion_requerida": requirement["description"],
            "familia": parsed.family.value,
            "cantidad_requerida": requested,
            "cantidad_asignada": 0.0,
            "cantidad_faltante": requested,
            "cobertura_pct": 0.0,
            "estado": ReconciliationStatus.NO_MATCH.value,
            "tipo_coincidencia": "NINGUNA",
            "score_coincidencia": 0.0,
            "codigos_inventario": "",
            "filas_inventario": "",
            "asignaciones_inventario": "",
            "descripcion_inventario": "",
            "stock_localizado": 0.0,
            "canonical_key": parsed.canonical_key,
            "canonical_key_inventario": "",
            "warnings": ", ".join(parsed.warnings),
            "warnings_inventario": "",
        }

        if requested <= 0:
            return base

        if parsed.family is MaterialFamily.UNKNOWN:
            base["estado"] = ReconciliationStatus.UNSEGMENTED.value
            return base

        candidates = [
            candidate
            for record in inventory
            if (candidate := self._candidate(parsed, record)) is not None
        ]
        exact_candidates = [
            candidate for candidate in candidates if candidate.exact
        ]
        exact_candidates.sort(
            key=lambda item: (
                item.record.remaining <= 0,
                -item.record.remaining,
                item.record.source_row,
            )
        )

        if exact_candidates:
            assigned_records = []
            allocation_details = []
            remaining_requirement = requested
            available_stock = sum(
                candidate.record.remaining for candidate in exact_candidates
            )
            for candidate in exact_candidates:
                available = candidate.record.remaining
                if available <= 0 or remaining_requirement <= 0:
                    continue
                allocated = min(available, remaining_requirement)
                candidate.record.remaining -= allocated
                remaining_requirement -= allocated
                assigned_records.append(candidate.record)
                allocation_details.append((candidate.record, allocated))

            assigned = requested - remaining_requirement
            base.update(
                {
                    "cantidad_asignada": assigned,
                    "cantidad_faltante": remaining_requirement,
                    "cobertura_pct": round(assigned / requested * 100, 2),
                    "tipo_coincidencia": "EXACTA",
                    "score_coincidencia": 1.0,
                    "stock_localizado": available_stock,
                }
            )
            display_records = assigned_records or [
                candidate.record for candidate in exact_candidates
            ]
            self._add_inventory_display(base, display_records)
            base["asignaciones_inventario"] = "; ".join(
                f"{record.code}: {allocated:g}"
                for record, allocated in allocation_details
            )
            if assigned >= requested:
                base["estado"] = ReconciliationStatus.COVERED.value
            elif assigned > 0:
                base["estado"] = (
                    ReconciliationStatus.PARTIAL_COVERAGE.value
                )
            else:
                base["estado"] = ReconciliationStatus.OUT_OF_STOCK.value
            return base

        partial_candidates = [
            candidate for candidate in candidates if not candidate.exact
        ]
        partial_candidates.sort(
            key=lambda item: (
                -item.score,
                item.record.remaining <= 0,
                -item.record.remaining,
                item.record.source_row,
            )
        )
        if partial_candidates:
            best = partial_candidates[0]
            base.update(
                {
                    "estado": ReconciliationStatus.REVIEW_REQUIRED.value,
                    "tipo_coincidencia": "PARCIAL",
                    "score_coincidencia": round(best.score, 2),
                    "stock_localizado": best.record.remaining,
                }
            )
            self._add_inventory_display(base, [best.record])
        return base

    def _candidate(
        self,
        requirement: ParsedMaterial,
        record: _InventoryRecord,
    ) -> _Candidate | None:
        inventory = record.parsed
        if inventory.family is not requirement.family:
            return None

        rules = self._rules_for(requirement)
        matched_weight = 0.0
        known_weight = 0.0
        known_anchors = 0
        for rule in rules:
            required_value = self._attribute(requirement, rule.name)
            if required_value is None:
                continue
            known_weight += rule.weight
            if rule.anchor:
                known_anchors += 1
            inventory_value = self._attribute(inventory, rule.name)
            if inventory_value is None:
                continue
            if not self._values_equal(required_value, inventory_value):
                return None
            matched_weight += rule.weight

        if known_weight == 0 or known_anchors == 0:
            return None
        score = matched_weight / known_weight
        if score < 0.55:
            return None

        exact = (
            score == 1.0
            and self._eligible_for_automatic_match(requirement)
            and self._eligible_for_automatic_match(inventory)
        )
        return _Candidate(record=record, score=score, exact=exact)

    @staticmethod
    def _rules_for(parsed: ParsedMaterial) -> tuple[_FieldRule, ...]:
        family = parsed.family
        if family is MaterialFamily.STUDS:
            return (
                _FieldRule("diametro", 3, True),
                _FieldRule("longitud", 3, True),
                _FieldRule("grado", 3),
            )
        if family is MaterialFamily.GASKETS:
            gasket_type = parsed.attributes.get("tipo")
            if gasket_type == "ANILLO":
                return (
                    _FieldRule("tipo", 4, True),
                    _FieldRule("numero_anillo", 5, True),
                    _FieldRule("material_base", 1),
                    _FieldRule("family_norm", 1),
                )
            rules = (
                _FieldRule("tipo", 4, True),
                _FieldRule("diametro", 3, True),
                _FieldRule("clase", 3, True),
                _FieldRule("cara", 1),
                _FieldRule("family_norm", 1),
            )
            if gasket_type == "ESPIROMETALICO":
                rules += (
                    _FieldRule("anillo_centrador", 1),
                    _FieldRule("anillo_interior", 1),
                )
            return rules
        if family is MaterialFamily.PIPE:
            return (
                _FieldRule("diametro", 4, True),
                _FieldRule("cedula", 3),
                _FieldRule("espesor", 2),
                _FieldRule("material_base", 3),
                _FieldRule("especificacion_material", 2),
                _FieldRule("fabricacion", 1),
                _FieldRule("extremos", 1),
                _FieldRule("family_norm", 1),
            )
        if family is MaterialFamily.FLANGES:
            return (
                _FieldRule("tipo_brida", 3, True),
                _FieldRule("diametro", 3, True),
                _FieldRule("clase", 3, True),
                _FieldRule("cedula", 2),
                _FieldRule("cara", 2),
                _FieldRule("material_base", 2),
                _FieldRule("especificacion_material", 1),
                _FieldRule("family_norm", 1),
            )
        if family is MaterialFamily.ELBOWS:
            return (
                _FieldRule("angulo", 3, True),
                _FieldRule("diametro", 3, True),
                _FieldRule("clase", 3),
                _FieldRule("cedula", 3),
                _FieldRule("radio", 1),
                _FieldRule("extremos", 2),
                _FieldRule("material_base", 2),
                _FieldRule("especificacion_material", 1),
                _FieldRule("family_norm", 2),
            )
        return ()

    @staticmethod
    def _attribute(parsed: ParsedMaterial, name: str) -> Any:
        if name == "cedula":
            number = parsed.attributes.get("cedula_num")
            if number is not None:
                return ("NUM", number)
            alias = parsed.attributes.get("cedula_alias")
            return ("ALIAS", alias) if alias is not None else None
        if name == "family_norm":
            standards = parsed.attributes.get("normas_cumplimiento", ())
            expected = {
                MaterialFamily.GASKETS: {"ASME B16.20"},
                MaterialFamily.PIPE: {"ASME B36.10"},
                MaterialFamily.FLANGES: {"ASME B16.5"},
                MaterialFamily.ELBOWS: {"ASME B16.9", "ASME B16.11"},
            }.get(parsed.family, set())
            selected = tuple(
                standard for standard in standards if standard in expected
            )
            return selected or None
        return parsed.attributes.get(name)

    @staticmethod
    def _values_equal(left: Any, right: Any) -> bool:
        if isinstance(left, float) or isinstance(right, float):
            try:
                return math.isclose(float(left), float(right), abs_tol=0.001)
            except (TypeError, ValueError):
                return False
        return left == right

    @staticmethod
    def _eligible_for_automatic_match(parsed: ParsedMaterial) -> bool:
        allowed_warnings = {"used_secondary_description"}
        return all(
            warning in allowed_warnings for warning in parsed.warnings
        )

    @staticmethod
    def _add_inventory_display(
        target: dict[str, Any],
        records: list[_InventoryRecord],
    ) -> None:
        unique_records = list(
            {record.source_row: record for record in records}.values()
        )
        target["codigos_inventario"] = ", ".join(
            record.code for record in unique_records
        )
        target["filas_inventario"] = ", ".join(
            str(record.source_row) for record in unique_records
        )
        target["descripcion_inventario"] = " | ".join(
            record.description for record in unique_records
        )
        target["canonical_key_inventario"] = " | ".join(
            dict.fromkeys(
                record.parsed.canonical_key
                for record in unique_records
                if record.parsed.canonical_key
            )
        )
        target["warnings_inventario"] = " | ".join(
            dict.fromkeys(
                ", ".join(record.parsed.warnings)
                for record in unique_records
                if record.parsed.warnings
            )
        )

    @staticmethod
    def _requirement_segmentation_row(
        requirement: dict[str, Any],
    ) -> dict[str, Any]:
        parsed: ParsedMaterial = requirement["parsed"]
        return {
            "fila_origen": requirement["source_row"],
            "udc": requirement["udc"],
            "fecha_programa": requirement["date"],
            "descripcion": requirement["description"],
            "descripcion_respaldo": requirement["secondary_description"],
            "cantidad_requerida": requirement["quantity"],
            "familia": parsed.family.value,
            "atributos": json.dumps(
                parsed.attributes,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "canonical_key": parsed.canonical_key,
            "confidence_score": parsed.confidence_score,
            "warnings": ", ".join(parsed.warnings),
        }

    @staticmethod
    def _inventory_segmentation_row(
        record: _InventoryRecord,
    ) -> dict[str, Any]:
        parsed = record.parsed
        return {
            "fila_origen": record.source_row,
            "codigo": record.code,
            "descripcion": record.description,
            "familia": parsed.family.value,
            "cantidad_inicial": record.quantity,
            "cantidad_asignada": record.allocated,
            "cantidad_restante": record.remaining,
            "atributos": json.dumps(
                parsed.attributes,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "canonical_key": parsed.canonical_key,
            "confidence_score": parsed.confidence_score,
            "warnings": ", ".join(parsed.warnings),
        }

    @staticmethod
    def _required_mapping(
        mappings: dict[str, str],
        key: str,
    ) -> str:
        try:
            return mappings[key]
        except KeyError as exc:
            raise ReconciliationError(
                "La configuracion de columnas esta incompleta."
            ) from exc

    @staticmethod
    def _text(value: Any) -> str:
        if value is None:
            return ""
        try:
            if bool(pd.isna(value)):
                return ""
        except (TypeError, ValueError):
            pass
        return str(value).strip()

    @staticmethod
    def _quantity(value: Any) -> float:
        try:
            quantity = pd.to_numeric(value, errors="coerce")
            if bool(pd.isna(quantity)):
                return 0.0
            quantity = float(quantity)
        except (TypeError, ValueError):
            return 0.0
        if not math.isfinite(quantity) or quantity < 0:
            return 0.0
        return quantity
