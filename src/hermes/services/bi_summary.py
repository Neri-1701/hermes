"""Business intelligence summaries for Hermes reconciliation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from hermes.domain.reconciliation import ReconciliationReport, ReconciliationStatus


@dataclass(frozen=True, slots=True)
class MetricCard:
    """Compact dashboard metric ready to be rendered in the UI."""

    title: str
    value: str
    detail: str
    level: str = "neutral"


@dataclass(frozen=True, slots=True)
class DistributionItem:
    """Named count and percentage used by dashboard distribution blocks."""

    label: str
    count: int
    percentage: float
    level: str = "neutral"


@dataclass(frozen=True, slots=True)
class ReconciliationDashboardSummary:
    """Aggregated BI data for one complete reconciliation run."""

    cards: tuple[MetricCard, ...]
    status_distribution: tuple[DistributionItem, ...]
    family_summary: pd.DataFrame
    critical_requirements: pd.DataFrame
    inventory_usage: pd.DataFrame
    coverage_pct: float
    covered_count: int
    requirement_count: int
    total_required: float
    total_assigned: float
    total_missing: float
    inventory_usage_pct: float
    inventory_initial: float
    inventory_assigned: float
    inventory_remaining: float


_STATUS_LABELS = {
    ReconciliationStatus.COVERED.value: "Cubiertos",
    ReconciliationStatus.PARTIAL_COVERAGE.value: "Cobertura parcial",
    ReconciliationStatus.OUT_OF_STOCK.value: "Sin existencia",
    ReconciliationStatus.REVIEW_REQUIRED.value: "Revision requerida",
    ReconciliationStatus.NO_MATCH.value: "Sin coincidencia",
    ReconciliationStatus.UNSEGMENTED.value: "No segmentado",
}

_STATUS_LEVELS = {
    ReconciliationStatus.COVERED.value: "success",
    ReconciliationStatus.PARTIAL_COVERAGE.value: "warning",
    ReconciliationStatus.OUT_OF_STOCK.value: "danger",
    ReconciliationStatus.REVIEW_REQUIRED.value: "warning",
    ReconciliationStatus.NO_MATCH.value: "danger",
    ReconciliationStatus.UNSEGMENTED.value: "warning",
}

_CRITICAL_STATUSES = {
    ReconciliationStatus.PARTIAL_COVERAGE.value,
    ReconciliationStatus.OUT_OF_STOCK.value,
    ReconciliationStatus.REVIEW_REQUIRED.value,
    ReconciliationStatus.NO_MATCH.value,
    ReconciliationStatus.UNSEGMENTED.value,
}


def build_reconciliation_dashboard_summary(
    report: ReconciliationReport,
) -> ReconciliationDashboardSummary:
    """Build relevant dashboard indicators from a reconciliation report."""
    matches = _safe_dataframe(report.matches)
    inventory = _safe_dataframe(report.inventory)

    total_required = _sum(matches, "cantidad_requerida")
    total_assigned = _sum(matches, "cantidad_asignada")
    total_missing = _sum(matches, "cantidad_faltante")

    requirement_count = len(matches)
    covered_count = _count_status(matches, ReconciliationStatus.COVERED.value)
    coverage_pct = _percentage(covered_count, requirement_count)
    review_count = _count_statuses(
        matches,
        {
            ReconciliationStatus.REVIEW_REQUIRED.value,
            ReconciliationStatus.UNSEGMENTED.value,
        },
    )
    critical_count = _count_statuses(matches, _CRITICAL_STATUSES)

    inventory_initial = _sum(inventory, "cantidad_inicial")
    inventory_assigned = _sum(inventory, "cantidad_asignada")
    inventory_remaining = _sum(inventory, "cantidad_restante")
    inventory_usage_pct = _percentage(inventory_assigned, inventory_initial)

    cards = (
        MetricCard(
            title="Cobertura de partidas",
            value=f"{coverage_pct:.1f}%",
            detail=f"{covered_count} de {requirement_count} partidas cubiertas",
            level=_coverage_level(coverage_pct),
        ),
        MetricCard(
            title="Requerimientos",
            value=str(requirement_count),
            detail=(
                f"{covered_count} cubiertos; "
                f"{review_count} requieren revision"
            ),
            level="neutral" if critical_count == 0 else "warning",
        ),
        MetricCard(
            title="Cantidad faltante",
            value=_format_quantity(total_missing),
            detail="Pendiente total despues del cruce",
            level="success" if total_missing == 0 else "danger",
        ),
        MetricCard(
            title="Inventario utilizado",
            value=f"{inventory_usage_pct:.1f}%",
            detail=(
                f"Restante {_format_quantity(inventory_remaining)} de "
                f"{_format_quantity(inventory_initial)}"
            ),
            level="neutral",
        ),
    )

    return ReconciliationDashboardSummary(
        cards=cards,
        status_distribution=_build_status_distribution(matches),
        family_summary=_build_family_summary(matches, inventory),
        critical_requirements=_build_critical_requirements(matches),
        inventory_usage=_build_inventory_usage(inventory),
        coverage_pct=coverage_pct,
        covered_count=covered_count,
        requirement_count=requirement_count,
        total_required=total_required,
        total_assigned=total_assigned,
        total_missing=total_missing,
        inventory_usage_pct=inventory_usage_pct,
        inventory_initial=inventory_initial,
        inventory_assigned=inventory_assigned,
        inventory_remaining=inventory_remaining,
    )


def _build_status_distribution(matches: pd.DataFrame) -> tuple[DistributionItem, ...]:
    total = len(matches)
    if total == 0 or "estado" not in matches.columns:
        return ()

    distribution = []
    for status, label in _STATUS_LABELS.items():
        count = _count_status(matches, status)
        if count == 0:
            continue
        distribution.append(
            DistributionItem(
                label=label,
                count=count,
                percentage=count / total * 100,
                level=_STATUS_LEVELS.get(status, "neutral"),
            )
        )
    return tuple(distribution)


def _build_family_summary(
    matches: pd.DataFrame,
    inventory: pd.DataFrame,
) -> pd.DataFrame:
    requirement_columns = [
        "familia",
        "cantidad_requerida",
        "cantidad_asignada",
        "cantidad_faltante",
        "estado",
    ]
    if matches.empty or not _has_columns(matches, requirement_columns):
        return _family_summary_empty()

    requirements_by_family = (
        matches[requirement_columns]
        .copy()
        .groupby("familia", dropna=False)
        .agg(
            requerimientos=("familia", "size"),
            cantidad_requerida=("cantidad_requerida", "sum"),
            cantidad_asignada=("cantidad_asignada", "sum"),
            cantidad_faltante=("cantidad_faltante", "sum"),
            partidas_cubiertas=(
                "estado",
                lambda values: int(
                    (values == ReconciliationStatus.COVERED.value).sum()
                ),
            ),
        )
        .reset_index()
    )

    if _has_columns(inventory, ["familia", "cantidad_inicial", "cantidad_restante"]):
        inventory_by_family = (
            inventory[["familia", "cantidad_inicial", "cantidad_restante"]]
            .copy()
            .groupby("familia", dropna=False)
            .agg(
                inventario_inicial=("cantidad_inicial", "sum"),
                inventario_restante=("cantidad_restante", "sum"),
            )
            .reset_index()
        )
    else:
        inventory_by_family = pd.DataFrame(
            columns=["familia", "inventario_inicial", "inventario_restante"]
        )

    summary = requirements_by_family.merge(
        inventory_by_family,
        on="familia",
        how="left",
    ).fillna({"inventario_inicial": 0.0, "inventario_restante": 0.0})
    summary["cobertura_partidas_pct"] = summary.apply(
        lambda row: _percentage(row["partidas_cubiertas"], row["requerimientos"]),
        axis=1,
    )
    summary["cobertura_cantidad_pct"] = summary.apply(
        lambda row: _percentage(row["cantidad_asignada"], row["cantidad_requerida"]),
        axis=1,
    )
    summary["inventario_utilizado"] = (
        summary["inventario_inicial"] - summary["inventario_restante"]
    )
    return summary.sort_values(
        by=["cantidad_faltante", "cantidad_requerida", "familia"],
        ascending=[False, False, True],
    ).reset_index(drop=True)


def _build_critical_requirements(matches: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "fila_requerimiento",
        "descripcion_requerida",
        "familia",
        "cantidad_requerida",
        "cantidad_asignada",
        "cantidad_faltante",
        "cobertura_pct",
        "estado",
        "tipo_coincidencia",
        "codigos_inventario",
        "motivo_decision",
    ]
    if matches.empty or "estado" not in matches.columns:
        return pd.DataFrame(columns=columns)

    available_columns = [column for column in columns if column in matches.columns]
    critical = matches[matches["estado"].isin(_CRITICAL_STATUSES)].copy()
    if critical.empty:
        return pd.DataFrame(columns=columns)

    sort_columns = [
        column
        for column in ["cantidad_faltante", "cobertura_pct", "fila_requerimiento"]
        if column in critical.columns
    ]
    ascending = [False, True, True][: len(sort_columns)]
    if sort_columns:
        critical = critical.sort_values(by=sort_columns, ascending=ascending)
    return critical[available_columns].head(50).reset_index(drop=True)


def _build_inventory_usage(inventory: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "familia",
        "codigo",
        "descripcion",
        "cantidad_inicial",
        "cantidad_asignada",
        "cantidad_restante",
        "uso_pct",
    ]
    required = [
        "familia",
        "codigo",
        "descripcion",
        "cantidad_inicial",
        "cantidad_asignada",
        "cantidad_restante",
    ]
    if inventory.empty or not _has_columns(inventory, required):
        return pd.DataFrame(columns=columns)

    usage = inventory[required].copy()
    usage["uso_pct"] = usage.apply(
        lambda row: _percentage(row["cantidad_asignada"], row["cantidad_inicial"]),
        axis=1,
    )
    return usage.sort_values(
        by=["cantidad_asignada", "cantidad_inicial", "familia"],
        ascending=[False, False, True],
    ).head(50).reset_index(drop=True)


def _family_summary_empty() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "familia",
            "requerimientos",
            "cantidad_requerida",
            "cantidad_asignada",
            "cantidad_faltante",
            "partidas_cubiertas",
            "inventario_inicial",
            "inventario_restante",
            "cobertura_partidas_pct",
            "cobertura_cantidad_pct",
            "inventario_utilizado",
        ]
    )


def _safe_dataframe(dataframe: pd.DataFrame | None) -> pd.DataFrame:
    if dataframe is None:
        return pd.DataFrame()
    return dataframe.copy()


def _has_columns(dataframe: pd.DataFrame, columns: Iterable[str]) -> bool:
    return all(column in dataframe.columns for column in columns)


def _sum(dataframe: pd.DataFrame, column: str) -> float:
    if dataframe.empty or column not in dataframe.columns:
        return 0.0
    return float(pd.to_numeric(dataframe[column], errors="coerce").fillna(0).sum())


def _count_status(dataframe: pd.DataFrame, status: str) -> int:
    if dataframe.empty or "estado" not in dataframe.columns:
        return 0
    return int((dataframe["estado"] == status).sum())


def _count_statuses(dataframe: pd.DataFrame, statuses: set[str]) -> int:
    if dataframe.empty or "estado" not in dataframe.columns:
        return 0
    return int(dataframe["estado"].isin(statuses).sum())


def _percentage(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator) * 100


def _coverage_level(coverage_pct: float) -> str:
    if coverage_pct >= 95:
        return "success"
    if coverage_pct >= 70:
        return "warning"
    return "danger"


def _format_quantity(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.2f}"
