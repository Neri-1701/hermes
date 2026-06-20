from __future__ import annotations

import pandas as pd

from hermes.domain.reconciliation import ReconciliationReport, ReconciliationStatus
from hermes.services.bi_summary import build_reconciliation_dashboard_summary


def test_build_reconciliation_dashboard_summary_aggregates_totals() -> None:
    report = ReconciliationReport(
        matches=pd.DataFrame(
            [
                {
                    "fila_requerimiento": 2,
                    "descripcion_requerida": "EMPAQUE 2 IN 150 RF",
                    "familia": "empaques",
                    "cantidad_requerida": 10,
                    "cantidad_asignada": 10,
                    "cantidad_faltante": 0,
                    "cobertura_pct": 100,
                    "estado": ReconciliationStatus.COVERED.value,
                    "tipo_coincidencia": "EXACTA",
                    "codigos_inventario": "A-001",
                    "motivo_decision": "campos_criticos_compatibles_sin_conflictos",
                },
                {
                    "fila_requerimiento": 3,
                    "descripcion_requerida": "TUBO 8 IN CED 80",
                    "familia": "tuberia",
                    "cantidad_requerida": 5,
                    "cantidad_asignada": 2,
                    "cantidad_faltante": 3,
                    "cobertura_pct": 40,
                    "estado": ReconciliationStatus.PARTIAL_COVERAGE.value,
                    "tipo_coincidencia": "EXACTA",
                    "codigos_inventario": "T-001",
                    "motivo_decision": "stock parcial",
                },
            ]
        ),
        requirements=pd.DataFrame(),
        inventory=pd.DataFrame(
            [
                {
                    "familia": "empaques",
                    "codigo": "A-001",
                    "descripcion": "EMPAQUE 2 IN 150 RF",
                    "cantidad_inicial": 12,
                    "cantidad_asignada": 10,
                    "cantidad_restante": 2,
                },
                {
                    "familia": "tuberia",
                    "codigo": "T-001",
                    "descripcion": "TUBO 8 IN CED 80",
                    "cantidad_inicial": 2,
                    "cantidad_asignada": 2,
                    "cantidad_restante": 0,
                },
            ]
        ),
    )

    summary = build_reconciliation_dashboard_summary(report)

    assert summary.total_required == 15
    assert summary.total_assigned == 12
    assert summary.total_missing == 3
    assert summary.covered_count == 1
    assert summary.requirement_count == 2
    assert summary.coverage_pct == 50
    assert summary.cards[0].value == "50.0%"
    assert summary.cards[0].detail == "1 de 2 partidas cubiertas"
    assert summary.status_distribution[0].label == "Cubiertos"
    assert summary.status_distribution[0].count == 1


def test_build_reconciliation_dashboard_summary_groups_by_family() -> None:
    report = ReconciliationReport(
        matches=pd.DataFrame(
            [
                {
                    "familia": "valvulas",
                    "cantidad_requerida": 4,
                    "cantidad_asignada": 1,
                    "cantidad_faltante": 3,
                    "cobertura_pct": 25,
                    "estado": ReconciliationStatus.PARTIAL_COVERAGE.value,
                },
                {
                    "familia": "valvulas",
                    "cantidad_requerida": 6,
                    "cantidad_asignada": 0,
                    "cantidad_faltante": 6,
                    "cobertura_pct": 0,
                    "estado": ReconciliationStatus.OUT_OF_STOCK.value,
                },
            ]
        ),
        requirements=pd.DataFrame(),
        inventory=pd.DataFrame(
            [
                {
                    "familia": "valvulas",
                    "codigo": "V-001",
                    "descripcion": "VALVULA",
                    "cantidad_inicial": 2,
                    "cantidad_asignada": 1,
                    "cantidad_restante": 1,
                }
            ]
        ),
    )

    summary = build_reconciliation_dashboard_summary(report)

    assert len(summary.family_summary) == 1
    family = summary.family_summary.iloc[0]
    assert family["familia"] == "valvulas"
    assert family["requerimientos"] == 2
    assert family["cantidad_requerida"] == 10
    assert family["cantidad_asignada"] == 1
    assert family["cantidad_faltante"] == 9
    assert family["partidas_cubiertas"] == 0
    assert family["cobertura_partidas_pct"] == 0
    assert family["cobertura_cantidad_pct"] == 10
    assert len(summary.critical_requirements) == 2
