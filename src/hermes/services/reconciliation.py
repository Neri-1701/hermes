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
    match_type: str
    acceptance_criteria: str
    decision_reason: str
    compatibility_level: str


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
        matches = pd.DataFrame(match_rows)
        requirement_segmentation = pd.DataFrame(
            self._requirement_segmentation_row(requirement)
            for requirement in requirements
        )
        inventory_segmentation = pd.DataFrame(
            self._inventory_segmentation_row(record)
            for record in inventory
        )
        return ReconciliationReport(
            matches=matches,
            requirements=requirement_segmentation,
            inventory=inventory_segmentation,
            user_report=self._build_user_report(
                requirements_dataset.dataframe,
                matches,
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
                        candidate.match_type
                    ),
                    "criterio_aceptacion": candidate.acceptance_criteria,
                    "motivo_decision": candidate.decision_reason,
                    "nivel_compatibilidad": candidate.compatibility_level,
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
                "criterio_aceptacion",
                "motivo_decision",
                "nivel_compatibilidad",
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
        secondary_column = (
            MaterialParser.item_column
            if (
                MaterialParser.item_column in dataframe.columns
                and MaterialParser.item_column != description_column
            )
            else ""
        )

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
            "descripcion_requerida": requirement["description"],
            "familia": parsed.family.value,
            "cantidad_requerida": requested,
            "cantidad_asignada": 0.0,
            "cantidad_faltante": requested,
            "cobertura_pct": 0.0,
            "estado": ReconciliationStatus.NO_MATCH.value,
            "tipo_coincidencia": "NINGUNA",
            "criterio_aceptacion": "",
            "motivo_decision": "",
            "nivel_compatibilidad": "NO_MATCH",
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
                    "tipo_coincidencia": exact_candidates[0].match_type,
                    "score_coincidencia": round(exact_candidates[0].score, 2),
                    "criterio_aceptacion": (
                        exact_candidates[0].acceptance_criteria
                    ),
                    "motivo_decision": exact_candidates[0].decision_reason,
                    "nivel_compatibilidad": (
                        exact_candidates[0].compatibility_level
                    ),
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
                    "tipo_coincidencia": best.match_type,
                    "criterio_aceptacion": best.acceptance_criteria,
                    "motivo_decision": best.decision_reason,
                    "nivel_compatibilidad": best.compatibility_level,
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
        compared_fields = 0
        superior_fields: list[str] = []
        skipped_optional_fields: list[str] = []
        for rule in rules:
            required_value = self._attribute(requirement, rule.name)
            inventory_value = self._attribute(inventory, rule.name)

            if rule.anchor and (
                required_value is None or inventory_value is None
            ):
                return None
            if required_value is None or inventory_value is None:
                if required_value is not None or inventory_value is not None:
                    skipped_optional_fields.append(rule.name)
                continue

            comparison = self._compare_values(
                rule.name,
                required_value,
                inventory_value,
            )
            if not comparison:
                return None
            known_weight += rule.weight
            matched_weight += rule.weight
            compared_fields += 1
            if comparison == "SUPERIOR":
                superior_fields.append(rule.name)

        if known_weight == 0 or compared_fields == 0:
            return None
        score = matched_weight / known_weight
        if score < 0.55:
            return None

        blocking_warnings = (
            self._blocking_warnings(requirement)
            | self._blocking_warnings(inventory)
        )
        exact = score == 1.0 and not blocking_warnings
        match_type = self._match_type(
            requirement,
            inventory,
            exact=exact,
            superior_fields=superior_fields,
            skipped_optional_fields=skipped_optional_fields,
        )
        return _Candidate(
            record=record,
            score=score,
            exact=exact,
            match_type=match_type,
            acceptance_criteria=self._acceptance_criteria(
                requirement.family,
                superior_fields,
                skipped_optional_fields,
            ),
            decision_reason=self._decision_reason(
                blocking_warnings,
                superior_fields,
                skipped_optional_fields,
                exact,
            ),
            compatibility_level=match_type,
        )

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
                _FieldRule("espesor_pared", 5, True),
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
                _FieldRule("espesor_pared", 2),
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
                _FieldRule("espesor_pared", 3),
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
        if name == "espesor_pared":
            return parsed.attributes.get("espesor_pared_in")
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
    def _compare_values(name: str, required: Any, inventory: Any) -> str | None:
        if name == "espesor_pared":
            try:
                required_float = float(required)
                inventory_float = float(inventory)
            except (TypeError, ValueError):
                return None
            if inventory_float + 0.005 < required_float:
                return None
            if inventory_float > required_float + 0.005:
                return "SUPERIOR"
            return "MATCH"
        if ReconciliationService._values_equal(required, inventory):
            return "MATCH"
        return None

    @staticmethod
    def _blocking_warnings(parsed: ParsedMaterial) -> set[str]:
        blocking = {
            "parse_error",
            "activity_description",
            "accessory_list",
            "schedule_thickness_conflict",
            "multiple_diameter_candidates",
        }
        return {warning for warning in parsed.warnings if warning in blocking}

    @staticmethod
    def _match_type(
        requirement: ParsedMaterial,
        inventory: ParsedMaterial,
        exact: bool,
        superior_fields: list[str],
        skipped_optional_fields: list[str],
    ) -> str:
        if not exact:
            return "VALIDACION_TECNICA"
        if superior_fields:
            return "ACEPTABLE_SUPERIOR"
        if skipped_optional_fields:
            return "ACEPTABLE_DIMENSIONALMENTE"
        if requirement.canonical_key and (
            requirement.canonical_key == inventory.canonical_key
        ):
            return "EXACTA"
        return "ACEPTABLE_DIMENSIONALMENTE"

    @staticmethod
    def _acceptance_criteria(
        family: MaterialFamily,
        superior_fields: list[str],
        skipped_optional_fields: list[str],
    ) -> str:
        if superior_fields:
            return "dimensiones_criticas_con_condicion_superior"
        if family is MaterialFamily.STUDS:
            return "diametro_y_longitud"
        if family is MaterialFamily.GASKETS:
            return "tipo_diametro_clase"
        if family is MaterialFamily.PIPE:
            return "diametro_y_espesor_pared"
        if family is MaterialFamily.FLANGES:
            return "tipo_diametro_clase"
        if family is MaterialFamily.ELBOWS:
            return "angulo_diametro_y_condicion_presion"
        return "atributos_comparables"

    @staticmethod
    def _decision_reason(
        blocking_warnings: set[str],
        superior_fields: list[str],
        skipped_optional_fields: list[str],
        exact: bool,
    ) -> str:
        if blocking_warnings:
            return "warnings_bloqueantes: " + ", ".join(
                sorted(blocking_warnings)
            )
        if superior_fields:
            return "inventario_igual_o_superior_en: " + ", ".join(
                superior_fields
            )
        if skipped_optional_fields:
            return "campos_opcionales_no_declarados: " + ", ".join(
                skipped_optional_fields
            )
        if exact:
            return "campos_criticos_compatibles_sin_conflictos"
        return "requiere_validacion_tecnica"

    @staticmethod
    def _values_equal(left: Any, right: Any) -> bool:
        if isinstance(left, float) or isinstance(right, float):
            try:
                return math.isclose(float(left), float(right), abs_tol=0.005)
            except (TypeError, ValueError):
                return False
        return left == right

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
    def _build_user_report(
        requirements_dataframe: pd.DataFrame,
        matches: pd.DataFrame,
    ) -> pd.DataFrame:
        """Return the end-user Excel table based on the original requirements."""
        report = requirements_dataframe.copy().reset_index(drop=True)
        if matches.empty:
            report["estado_asignacion"] = ""
            report["tipo_coincidencia"] = ""
            report["criterio_aceptacion"] = ""
            report["motivo_decision"] = ""
            report["nivel_compatibilidad"] = ""
            report["codigo(s) asignado(s)"] = ""
            report["descripcion(es) asignada(s)"] = ""
            report["cantidad(es) asignada(s)"] = ""
            report["cantidad_total_asignada"] = 0.0
            report["cantidad_faltante"] = 0.0
            return report

        aligned = matches.reset_index(drop=True)
        report["estado_asignacion"] = aligned["estado"]
        report["tipo_coincidencia"] = aligned["tipo_coincidencia"]
        report["criterio_aceptacion"] = aligned["criterio_aceptacion"]
        report["motivo_decision"] = aligned["motivo_decision"]
        report["nivel_compatibilidad"] = aligned["nivel_compatibilidad"]
        report["codigo(s) asignado(s)"] = aligned["codigos_inventario"]
        report["descripcion(es) asignada(s)"] = aligned["descripcion_inventario"]
        report["cantidad(es) asignada(s)"] = aligned["asignaciones_inventario"]
        report["cantidad_total_asignada"] = aligned["cantidad_asignada"]
        report["cantidad_faltante"] = aligned["cantidad_faltante"]
        return report

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
