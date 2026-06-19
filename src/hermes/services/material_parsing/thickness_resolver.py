"""Resolve pipe schedule notation to canonical wall thickness."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
import math
from pathlib import Path


TABLE_VERSION = "pipe_wall_thickness_reference_hermes_0_4_0"
THICKNESS_TOLERANCE_IN = 0.005


@dataclass(frozen=True, slots=True)
class ThicknessRow:
    """One schedule-to-wall-thickness reference row."""

    nps_value: float
    schedule_normalized: str
    wall_in: float
    wall_mm: float
    standard_family: str
    material_group: str


@dataclass(frozen=True, slots=True)
class ThicknessResolution:
    """Canonical thickness fields added to parsed material attributes."""

    espesor_pared_in: float | None
    espesor_pared_mm: float | None
    fuente_espesor: str
    tabla_espesor_version: str
    validacion_cedula: str
    warnings: tuple[str, ...] = ()
    cedula_inferida: str | None = None


class ThicknessResolver:
    """Convert schedule/explicit thickness input into canonical wall thickness."""

    def __init__(self, rows: tuple[ThicknessRow, ...] | None = None) -> None:
        self._rows = rows or _load_default_rows()

    def resolve(
        self,
        diameter: float | None,
        schedule_number: int | None = None,
        schedule_alias: str | None = None,
        explicit_thickness: float | None = None,
        material_base: str | None = None,
    ) -> ThicknessResolution:
        """Resolve canonical wall thickness using the Hermes operative table."""
        explicit = _clean_float(explicit_thickness)
        schedule_rows = self._matching_schedule_rows(
            diameter,
            schedule_number,
            schedule_alias,
            material_base,
        )

        if explicit is not None:
            inferred = self._infer_schedule(diameter, explicit, material_base)
            if not schedule_number and not schedule_alias:
                return ThicknessResolution(
                    espesor_pared_in=explicit,
                    espesor_pared_mm=round(explicit * 25.4, 2),
                    fuente_espesor="EXPLICITO",
                    tabla_espesor_version=TABLE_VERSION,
                    validacion_cedula="NO_APLICA",
                    cedula_inferida=(
                        inferred.schedule_normalized if inferred else None
                    ),
                )
            if not schedule_rows:
                return ThicknessResolution(
                    espesor_pared_in=explicit,
                    espesor_pared_mm=round(explicit * 25.4, 2),
                    fuente_espesor="EXPLICITO",
                    tabla_espesor_version=TABLE_VERSION,
                    validacion_cedula="CEDULA_NO_ENCONTRADA",
                    warnings=("schedule_thickness_not_found",),
                    cedula_inferida=(
                        inferred.schedule_normalized if inferred else None
                    ),
                )
            if any(_same_thickness(row.wall_in, explicit) for row in schedule_rows):
                return ThicknessResolution(
                    espesor_pared_in=explicit,
                    espesor_pared_mm=round(explicit * 25.4, 2),
                    fuente_espesor="EXPLICITO_VALIDADO_CON_CEDULA",
                    tabla_espesor_version=TABLE_VERSION,
                    validacion_cedula="OK",
                    cedula_inferida=(
                        inferred.schedule_normalized if inferred else None
                    ),
                )
            return ThicknessResolution(
                espesor_pared_in=explicit,
                espesor_pared_mm=round(explicit * 25.4, 2),
                fuente_espesor="CONFLICTO",
                tabla_espesor_version=TABLE_VERSION,
                validacion_cedula="CONFLICTO",
                warnings=("schedule_thickness_conflict",),
                cedula_inferida=inferred.schedule_normalized if inferred else None,
            )

        if schedule_number or schedule_alias:
            if not schedule_rows:
                return ThicknessResolution(
                    espesor_pared_in=None,
                    espesor_pared_mm=None,
                    fuente_espesor="NO_RESUELTO",
                    tabla_espesor_version=TABLE_VERSION,
                    validacion_cedula="CEDULA_NO_ENCONTRADA",
                    warnings=("schedule_thickness_not_found",),
                )
            selected = schedule_rows[0]
            return ThicknessResolution(
                espesor_pared_in=selected.wall_in,
                espesor_pared_mm=selected.wall_mm,
                fuente_espesor="INFERIDO_DESDE_CEDULA",
                tabla_espesor_version=TABLE_VERSION,
                validacion_cedula="OK",
            )

        return ThicknessResolution(
            espesor_pared_in=None,
            espesor_pared_mm=None,
            fuente_espesor="NO_RESUELTO",
            tabla_espesor_version=TABLE_VERSION,
            validacion_cedula="NO_APLICA",
        )

    def _matching_schedule_rows(
        self,
        diameter: float | None,
        schedule_number: int | None,
        schedule_alias: str | None,
        material_base: str | None,
    ) -> list[ThicknessRow]:
        if diameter is None:
            return []
        tokens = _schedule_tokens(schedule_number, schedule_alias)
        if not tokens:
            return []
        candidates = [
            row
            for row in self._rows
            if math.isclose(row.nps_value, diameter, abs_tol=1e-8)
            and row.schedule_normalized in tokens
        ]
        return _rank_rows(candidates, material_base, tokens)

    def _infer_schedule(
        self,
        diameter: float | None,
        thickness: float,
        material_base: str | None,
    ) -> ThicknessRow | None:
        if diameter is None:
            return None
        candidates = [
            row
            for row in self._rows
            if math.isclose(row.nps_value, diameter, abs_tol=1e-8)
            and _same_thickness(row.wall_in, thickness)
        ]
        ranked = _rank_rows(candidates, material_base, ())
        return ranked[0] if ranked else None


def add_resolved_thickness(
    attributes: dict[str, object],
    warnings: list[str],
    resolver: ThicknessResolver | None = None,
) -> None:
    """Add canonical thickness attributes and schedule validation warnings."""
    resolver = resolver or ThicknessResolver()
    diameter = attributes.get("diametro")
    material_base = attributes.get("material_base")
    resolution = resolver.resolve(
        diameter=diameter if isinstance(diameter, float) else None,
        schedule_number=(
            attributes["cedula_num"]
            if isinstance(attributes.get("cedula_num"), int)
            else None
        ),
        schedule_alias=(
            attributes["cedula_alias"]
            if isinstance(attributes.get("cedula_alias"), str)
            else None
        ),
        explicit_thickness=(
            attributes["espesor"]
            if isinstance(attributes.get("espesor"), float)
            else None
        ),
        material_base=material_base if isinstance(material_base, str) else None,
    )
    attributes["fuente_espesor"] = resolution.fuente_espesor
    attributes["tabla_espesor_version"] = resolution.tabla_espesor_version
    attributes["validacion_cedula"] = resolution.validacion_cedula
    if resolution.espesor_pared_in is not None:
        attributes["espesor_pared_in"] = resolution.espesor_pared_in
    if resolution.espesor_pared_mm is not None:
        attributes["espesor_pared_mm"] = resolution.espesor_pared_mm
    if resolution.cedula_inferida is not None:
        attributes["cedula_inferida"] = resolution.cedula_inferida
    for warning in resolution.warnings:
        if warning not in warnings:
            warnings.append(warning)


@lru_cache(maxsize=1)
def _load_default_rows() -> tuple[ThicknessRow, ...]:
    path = resources.files("hermes.resources").joinpath(
        "pipe_wall_thickness_reference.csv"
    )
    with path.open("r", encoding="utf-8", newline="") as handle:
        return _load_rows(handle)


def load_rows_from_path(path: Path) -> tuple[ThicknessRow, ...]:
    """Load reference rows from a CSV path, useful for tests and scripts."""
    with path.open("r", encoding="utf-8", newline="") as handle:
        return _load_rows(handle)


def _load_rows(handle) -> tuple[ThicknessRow, ...]:
    reader = csv.DictReader(handle)
    return tuple(
        ThicknessRow(
            nps_value=float(row["nps_value"]),
            schedule_normalized=_normalize_schedule_token(
                row["schedule_normalized"]
            ),
            wall_in=float(row["wall_in"]),
            wall_mm=float(row["wall_mm"]),
            standard_family=row["standard_family"],
            material_group=row["material_group"],
        )
        for row in reader
    )


def _schedule_tokens(
    number: int | None,
    alias: str | None,
) -> tuple[str, ...]:
    tokens: list[str] = []
    if alias:
        tokens.append(_normalize_schedule_token(alias))
    if number is not None:
        tokens.append(str(number))
    return tuple(dict.fromkeys(tokens))


def _normalize_schedule_token(value: str) -> str:
    token = value.strip().upper()
    if token.isdigit():
        return str(int(token))
    return token


def _rank_rows(
    rows: list[ThicknessRow],
    material_base: str | None,
    tokens: tuple[str, ...],
) -> list[ThicknessRow]:
    return sorted(
        rows,
        key=lambda row: (
            _material_rank(row, material_base, tokens),
            row.schedule_normalized not in tokens if tokens else False,
            row.schedule_normalized,
        ),
    )


def _material_rank(
    row: ThicknessRow,
    material_base: str | None,
    tokens: tuple[str, ...],
) -> int:
    token_has_s = any(token.endswith("S") for token in tokens)
    material = material_base or ""
    if token_has_s and row.standard_family == "B36.19M_LIKE":
        return 0
    if "INOXIDABLE" in material and row.standard_family == "B36.19M_LIKE":
        return 0
    if row.standard_family == "B36.10M_LIKE":
        return 1
    return 2


def _clean_float(value: float | None) -> float | None:
    if value is None:
        return None
    if not math.isfinite(value):
        return None
    return value


def _same_thickness(left: float, right: float) -> bool:
    return math.isclose(left, right, abs_tol=THICKNESS_TOLERANCE_IN)
