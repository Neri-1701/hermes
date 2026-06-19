from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from hermes.domain.models import DataSource, HermesState, LoadedDataset
from hermes.domain.reconciliation import ReconciliationStatus
from hermes.services.reconciliation import ReconciliationService

STUD_B7 = (
    "ESPARRAGO ASTM A193/A193M GRADO B7, "
    'DE 3/4" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
)
STUD_B7_WITHOUT_GRADE = (
    'ESPARRAGO, DE 3/4" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
)
PIPE = (
    'TUBO, DE 2" DE DIAMETRO NOMINAL, DE 0.218" DE ESPESOR, '
    "CEDULA (XS, 080), DE ACERO AL CARBONO, "
    "ASTM A106/A106M GRADO B"
)
PIPE_8_SCH_40 = (
    'TUBO, DE 8" DE DIAMETRO NOMINAL, SCH 40, '
    "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
)
PIPE_8_EXPLICIT_0322 = (
    'TUBO, DE 8" DE DIAMETRO NOMINAL, ESPESOR DE 0.322", '
    "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
)
PIPE_12_STD = (
    'TUBO, DE 12" DE DIAMETRO NOMINAL, CEDULA STD, '
    "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
)
PIPE_12_SCH_40 = (
    'TUBO, DE 12" DE DIAMETRO NOMINAL, SCH 40, '
    "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
)
GASKET = (
    'EMPAQUE, DE 3" DE DIAMETRO NOMINAL, CLASE 150, '
    "TIPO ESPIROMETALICO, CON ANILLO CENTRADOR Y ANILLO INTERIOR, "
    "CARA REALZADA (-RF), ASME B16.20"
)
FLANGE = (
    'BRIDA, CUELLO SOLDABLE (-WN), DE 2" DE DIAMETRO NOMINAL, '
    '0.218" DE ESPESOR, CEDULA (XS, 080), CLASE 150, '
    "CARA REALZADA (-RF), DE ACERO AL CARBONO, "
    "ASTM A105/A105M, ASME B16.5"
)
ELBOW = (
    'CODO, 90 GRADOS, DE 2" DE DIAMETRO NOMINAL, CLASE 3000, '
    "EXTREMOS INSERTO SOLDABLE, DE ACERO AL CARBONO, "
    "ASTM A105/A105M, ASME B16.11"
)


def _state(
    inventory: pd.DataFrame,
    requirements: pd.DataFrame,
) -> HermesState:
    state = HermesState()
    state.set_dataset(
        LoadedDataset(
            DataSource.INVENTORY,
            Path("inventory.xlsx"),
            inventory,
        )
    )
    state.set_dataset(
        LoadedDataset(
            DataSource.REQUIREMENTS,
            Path("requirements.xlsx"),
            requirements,
        )
    )
    mappings = {
        "inventory_description": "description",
        "inventory_code": "code",
        "inventory_quantity": "available",
        "requirements_description": "description",
        "requirements_quantity": "required",
    }
    for key, column in mappings.items():
        state.set_mapping(key, column)
    return state


def _inventory_state(inventory: pd.DataFrame) -> HermesState:
    state = HermesState()
    state.set_dataset(
        LoadedDataset(
            DataSource.INVENTORY,
            Path("inventory.xlsx"),
            inventory,
        )
    )
    for key, column in {
        "inventory_description": "description",
        "inventory_code": "code",
        "inventory_quantity": "available",
    }.items():
        state.set_mapping(key, column)
    return state


def test_quick_search_uses_canonical_rules_without_requirements_file() -> None:
    state = _inventory_state(
        pd.DataFrame(
            {
                "description": [STUD_B7, PIPE],
                "code": ["E-1", "T-1"],
                "available": [10, 8],
            }
        )
    )

    results = ReconciliationService().search_inventory(state, STUD_B7)

    assert results["codigo"].tolist() == ["E-1"]
    assert results.iloc[0]["tipo_coincidencia"] == "EXACTA"
    assert results.iloc[0]["score_coincidencia"] == 1
    assert results.iloc[0]["cantidad_disponible"] == 10


@pytest.mark.parametrize(
    ("description", "code"),
    (
        (STUD_B7, "E-1"),
        (GASKET, "G-1"),
        (PIPE, "T-1"),
        (FLANGE, "B-1"),
        (ELBOW, "C-1"),
    ),
)
def test_quick_search_supports_every_parser_family(
    description: str,
    code: str,
) -> None:
    state = _inventory_state(
        pd.DataFrame(
            {
                "description": [description],
                "code": [code],
                "available": [4],
            }
        )
    )

    results = ReconciliationService().search_inventory(state, description)

    assert results["codigo"].tolist() == [code]
    assert results.iloc[0]["tipo_coincidencia"] == "EXACTA"
    assert results.iloc[0]["canonical_key_busqueda"]
    assert results.iloc[0]["canonical_key_inventario"]


def test_quick_search_returns_partial_matches_for_incomplete_query() -> None:
    state = _inventory_state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [10],
            }
        )
    )

    results = ReconciliationService().search_inventory(
        state,
        STUD_B7_WITHOUT_GRADE,
    )

    assert results["codigo"].tolist() == ["E-1"]
    assert results.iloc[0]["tipo_coincidencia"] == "ACEPTABLE_DIMENSIONALMENTE"
    assert results.iloc[0]["score_coincidencia"] == 1
    assert "missing_grado" in results.iloc[0]["warnings_busqueda"]


def test_quick_search_does_not_modify_inventory_quantity() -> None:
    state = _inventory_state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [10],
            }
        )
    )
    service = ReconciliationService()

    first = service.search_inventory(state, STUD_B7)
    second = service.search_inventory(state, STUD_B7)

    assert first.iloc[0]["cantidad_disponible"] == 10
    assert second.iloc[0]["cantidad_disponible"] == 10


def test_quick_search_returns_empty_table_for_unrecognized_material() -> None:
    state = _inventory_state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [10],
            }
        )
    )

    results = ReconciliationService().search_inventory(
        state,
        "MATERIAL SIN DATOS TECNICOS",
    )

    assert results.empty
    assert "codigo" in results.columns


def test_allocates_exact_matches_without_reusing_inventory() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7, STUD_B7],
                "code": ["E-1", "E-2"],
                "available": [3, 4],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1", "U-2"],
                "date": ["2026-06-15", "2026-06-16"],
                "description": [STUD_B7, STUD_B7],
                "required": [5, 4],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches["estado"].tolist() == [
        ReconciliationStatus.COVERED.value,
        ReconciliationStatus.PARTIAL_COVERAGE.value,
    ]
    assert report.matches["cantidad_asignada"].tolist() == [5.0, 2.0]
    assert report.matches["stock_localizado"].tolist() == [7.0, 2.0]
    assert report.inventory["cantidad_asignada"].sum() == 7
    assert report.inventory["cantidad_restante"].sum() == 0
    assert report.matches.iloc[0]["codigos_inventario"] == "E-2, E-1"
    assert report.matches.iloc[0]["asignaciones_inventario"] == (
        "E-2: 4; E-1: 1"
    )
    assert report.user_report["udc"].tolist() == ["U-1", "U-2"]
    assert report.user_report.iloc[0]["codigo(s) asignado(s)"] == "E-2, E-1"
    assert report.user_report.iloc[0]["cantidad(es) asignada(s)"] == (
        "E-2: 4; E-1: 1"
    )


def test_matches_schedule_against_explicit_wall_thickness() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [PIPE_8_EXPLICIT_0322],
                "code": ["T-8"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "description": [PIPE_8_SCH_40],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.COVERED.value
    assert report.matches.iloc[0]["codigos_inventario"] == "T-8"


def test_does_not_match_std_and_schedule_40_globally() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [PIPE_12_STD],
                "code": ["T-STD"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "description": [PIPE_12_SCH_40],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_matches_inventory_with_equal_or_greater_wall_thickness() -> None:
    requirement = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, SCH 40, '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )
    inventory = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, ESPESOR DE 0.375", '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["T-8-XS"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.COVERED.value
    assert report.matches.iloc[0]["tipo_coincidencia"] == "ACEPTABLE_SUPERIOR"
    assert report.matches.iloc[0]["codigos_inventario"] == "T-8-XS"


def test_rejects_inventory_with_lower_wall_thickness() -> None:
    requirement = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, SCH 40, '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )
    inventory = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, ESPESOR DE 0.250", '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["T-8-LIGHT"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_gasket_missing_norm_is_operationally_acceptable() -> None:
    requirement = (
        'EMPAQUE, DE 3" DE DIAMETRO NOMINAL, CLASE 150, '
        "TIPO ESPIROMETALICO, CARA REALZADA (-RF), ASME B16.20"
    )
    inventory = (
        'EMPAQUE, DE 3" DE DIAMETRO NOMINAL, CLASE 150, '
        "TIPO ESPIROMETALICO, CARA REALZADA (-RF)"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["G-3"],
                "available": [4],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.COVERED.value
    assert report.matches.iloc[0]["tipo_coincidencia"] == (
        "ACEPTABLE_DIMENSIONALMENTE"
    )


def test_flange_rejects_different_class() -> None:
    requirement = FLANGE
    inventory = FLANGE.replace("CLASE 150", "CLASE 300")
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["B-300"],
                "available": [1],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_flange_rejects_different_face() -> None:
    requirement = FLANGE
    inventory = FLANGE.replace("CARA REALZADA (-RF)", "JUNTA DE ANILLO (-RTJ)")
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["B-RTJ"],
                "available": [1],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_additional_nace_standard_does_not_penalize_match() -> None:
    inventory = (
        PIPE
        + ", ANSI/NACE MR0175/ISO 15156-2"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["T-NACE"],
                "available": [1],
            }
        ),
        pd.DataFrame(
            {
                "description": [PIPE],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.COVERED.value
    assert report.matches.iloc[0]["score_coincidencia"] == 1


def test_butt_weld_elbow_does_not_cross_socket_weld_elbow() -> None:
    requirement = (
        'CODO, 90 GRADOS, DE 2" DE DIAMETRO NOMINAL, CEDULA 80, '
        "EXTREMOS BISELADOS, DE ACERO AL CARBONO, ASME B16.9"
    )
    inventory = (
        'CODO, 90 GRADOS, DE 2" DE DIAMETRO NOMINAL, CLASE 3000, '
        "EXTREMOS INSERTO SOLDABLE, DE ACERO AL CARBONO, ASME B16.11"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["C-SW"],
                "available": [1],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_elbow_uses_wall_thickness_over_schedule_notation() -> None:
    requirement = (
        "CODO DE 90 GRADOS, R.L., ACERO AL CARBONO S/COSTURA, "
        "EXTREMOS BISELADOS PARA SOLDAR, ESPECIFICACION ASTM-A-234, "
        'GRADO WPB, DE CEDULA 80 DE 4" Ø. ASME/ANSI B16.9'
    )
    inventory = (
        'CODO, DE ACERO AL CARBONO, SIN RECUBRIMIENTO, DE 4.00" '
        'DE DIAMETRO NOMINAL, 0.337" DE ESPESOR, CEDULA: (080) (-XS), '
        "SIN COSTURA, TIPO: 90 GRADOS, RADIO LARGO, EXTREMOS: BISELADOS, "
        "ESPECIFICACION: ASTM A234, GRADO: WPB, ASME: B16.9."
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["C-4-80"],
                "available": [1],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.COVERED.value
    assert report.matches.iloc[0]["tipo_coincidencia"] == (
        "ACEPTABLE_DIMENSIONALMENTE"
    )
    assert report.matches.iloc[0]["codigos_inventario"] == "C-4-80"


def test_missing_optional_attribute_does_not_penalize_score() -> None:
    requirement = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, SCH 40, '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )
    inventory = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, ESPESOR DE 0.322", '
        "DE ACERO AL CARBONO"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["T-8"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.COVERED.value
    assert report.matches.iloc[0]["score_coincidencia"] == 1
    assert report.matches.iloc[0]["codigos_inventario"] == "T-8"


def test_conflicting_optional_attribute_rejects_candidate() -> None:
    requirement = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, SCH 40, '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )
    inventory = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, ESPESOR DE 0.322", '
        "DE ACERO AL CARBONO, ASTM A53/A53M GRADO B"
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["T-8"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_missing_anchor_attribute_rejects_candidate() -> None:
    requirement = (
        'TUBO, DE 8" DE DIAMETRO NOMINAL, SCH 40, '
        "DE ACERO AL CARBONO"
    )
    inventory = 'TUBO, DE 8" DE DIAMETRO NOMINAL, DE ACERO AL CARBONO'
    state = _state(
        pd.DataFrame(
            {
                "description": [inventory],
                "code": ["T-8"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "description": [requirement],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == ReconciliationStatus.NO_MATCH.value
    assert report.matches.iloc[0]["codigos_inventario"] == ""


def test_missing_stud_grade_is_operationally_acceptable() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [10],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [STUD_B7_WITHOUT_GRADE],
                "required": [2],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)
    match = report.matches.iloc[0]

    assert match["estado"] == ReconciliationStatus.COVERED.value
    assert match["tipo_coincidencia"] == "ACEPTABLE_DIMENSIONALMENTE"
    assert match["score_coincidencia"] == 1
    assert match["cantidad_asignada"] == 2
    assert match["codigos_inventario"] == "E-1"
    assert report.inventory.iloc[0]["cantidad_restante"] == 8


def test_conflicting_technical_attributes_are_not_suggested() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [PIPE],
                "code": ["T-1"],
                "available": [8],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [
                    PIPE.replace('DE 2"', 'DE 3"').replace(
                        '0.218"',
                        '0.300"',
                    )
                ],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)
    match = report.matches.iloc[0]

    assert match["estado"] == ReconciliationStatus.NO_MATCH.value
    assert match["codigos_inventario"] == ""


def test_parser_conflict_prevents_automatic_inventory_assignment() -> None:
    conflicting_pipe = PIPE.replace('0.218"', '0.300"')
    state = _state(
        pd.DataFrame(
            {
                "description": [conflicting_pipe],
                "code": ["T-1"],
                "available": [8],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [conflicting_pipe],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)
    match = report.matches.iloc[0]

    assert match["estado"] == ReconciliationStatus.REVIEW_REQUIRED.value
    assert match["tipo_coincidencia"] == "VALIDACION_TECNICA"
    assert match["cantidad_asignada"] == 0


def test_uses_named_secondary_description_to_complete_requirement() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [PIPE],
                "code": ["T-1"],
                "available": [2],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": ['TUBO, DE 2" DE DIAMETRO NOMINAL'],
                "Data_DescripcionPartida": [
                    'DE 0.218" DE ESPESOR, CEDULA (XS, 080), '
                    "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
                ],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == (
        ReconciliationStatus.COVERED.value
    )
    assert "used_secondary_description" in (
        report.requirements.iloc[0]["warnings"]
    )


def test_reports_unsegmented_requirement_without_inventory_assignment() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [10],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": ["INSTALACION DE SOPORTES"],
                "required": [2],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == (
        ReconciliationStatus.UNSEGMENTED.value
    )
    assert report.inventory.iloc[0]["cantidad_asignada"] == 0


@pytest.mark.parametrize("quantity", ("abc", -1, float("nan")))
def test_coerces_invalid_requirement_quantities_to_zero(
    quantity: object,
) -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [10],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [STUD_B7],
                "required": [quantity],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)
    match = report.matches.iloc[0]

    assert match["cantidad_requerida"] == 0
    assert match["cantidad_asignada"] == 0
    assert match["cantidad_faltante"] == 0
    assert match["cobertura_pct"] == 0
    assert report.inventory.iloc[0]["cantidad_restante"] == 10
    assert "cobertura total 0.0%" in report.build_summary()


@pytest.mark.parametrize("quantity", ("abc", -1, float("nan")))
def test_coerces_invalid_inventory_quantities_to_zero(
    quantity: object,
) -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7],
                "code": ["E-1"],
                "available": [quantity],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [STUD_B7],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == (
        ReconciliationStatus.OUT_OF_STOCK.value
    )
    assert report.matches.iloc[0]["cantidad_asignada"] == 0
    assert report.inventory.iloc[0]["cantidad_inicial"] == 0
    assert report.inventory.iloc[0]["cantidad_restante"] == 0


def test_skips_inventory_rows_without_code() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7, STUD_B7],
                "code": [None, "E-1"],
                "available": ["invalid", 10],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [STUD_B7],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.matches.iloc[0]["estado"] == (
        ReconciliationStatus.COVERED.value
    )
    assert report.matches.iloc[0]["codigos_inventario"] == "E-1"
    assert report.matches.iloc[0]["filas_inventario"] == "3"
    assert report.inventory["fila_origen"].tolist() == [3]


def test_all_inventory_rows_without_code_produce_empty_search() -> None:
    state = _state(
        pd.DataFrame(
            {
                "description": [STUD_B7, None],
                "code": [None, ""],
                "available": ["invalid", -5],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1"],
                "date": ["2026-06-15"],
                "description": [STUD_B7],
                "required": [1],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert report.inventory.empty
    assert report.matches.iloc[0]["estado"] == (
        ReconciliationStatus.NO_MATCH.value
    )
    assert report.matches.iloc[0]["cantidad_asignada"] == 0


def test_dirty_rows_do_not_stop_valid_allocations() -> None:
    malformed = (
        "ESPARRAGO ASTM A193 GRADO B7, "
        'DE 1/0" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
    )
    state = _state(
        pd.DataFrame(
            {
                "description": [
                    STUD_B7,
                    malformed,
                    STUD_B7,
                    None,
                ],
                "code": ["E-1", "E-BAD", "E-2", None],
                "available": [2, "sin cantidad", 4, 100],
            }
        ),
        pd.DataFrame(
            {
                "udc": ["U-1", "U-2", "U-3"],
                "date": ["2026-06-15", None, "2026-06-17"],
                "description": [STUD_B7, malformed, STUD_B7],
                "required": [3, "sin cantidad", 2],
            }
        ),
    )

    report = ReconciliationService().reconcile(state)

    assert len(report.matches) == 3
    assert report.matches["cantidad_asignada"].tolist() == [3.0, 0.0, 2.0]
    assert report.matches["estado"].tolist() == [
        ReconciliationStatus.COVERED.value,
        ReconciliationStatus.NO_MATCH.value,
        ReconciliationStatus.COVERED.value,
    ]
    assert report.requirements.iloc[1]["familia"] == "UNKNOWN"
    assert "parse_error" in report.requirements.iloc[1]["warnings"]
    assert report.inventory["fila_origen"].tolist() == [2, 3, 4]
    assert report.inventory["cantidad_restante"].tolist() == [0.0, 0.0, 1.0]
