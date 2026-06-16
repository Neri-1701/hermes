from __future__ import annotations

import pandas as pd
import pytest

from hermes.domain.materials import MaterialFamily
from hermes.services.material_parser import MaterialParser
from hermes.services.material_parsing.normalizer import normalize_text
from hermes.services.material_parsing.universal import parse_inch_number


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        ('3/4"', 0.75),
        ('1-1/2"', 1.5),
        ('1 1/2"', 1.5),
        ('0.218"', 0.218),
    ),
)
def test_parses_all_required_inch_formats(source: str, expected: float) -> None:
    assert parse_inch_number(source) == expected


def test_normalization_preserves_raw_text_and_evidence_offsets() -> None:
    source = "  Brída Ø 2º_x000D_\n"
    normalized = normalize_text(source)
    diameter_start = normalized.text.index("DIAMETRO")
    evidence = normalized.evidence(
        "diametro_contexto",
        diameter_start,
        diameter_start + len("DIAMETRO"),
    )

    assert normalized.raw == source
    assert normalized.text == "BRIDA DIAMETRO 2 GRADOS"
    assert evidence.text == "Ø"
    assert source[evidence.start : evidence.end] == evidence.text


def test_normalization_accepts_typographic_inch_quotes_and_hyphens() -> None:
    parsed = MaterialParser().parse_description(
        "ESPARRAGO ASTM A193 GRADO B7, "
        "DE 1–1/2” DE DIAMETRO NOMINAL X 5” DE LONGITUD"
    )

    assert parsed.attributes["diametro"] == 1.5
    assert parsed.attributes["longitud"] == 5


def test_malformed_fraction_returns_review_result_instead_of_raising() -> None:
    parsed = MaterialParser().parse_description(
        "ESPARRAGO ASTM A193 GRADO B7, "
        'DE 1/0" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
    )

    assert parsed.family is MaterialFamily.UNKNOWN
    assert parsed.attributes == {}
    assert "parse_error" in parsed.warnings
    assert "review_required" in parsed.warnings


def test_extracts_stud_dimensions_after_diameter_and_specific_grade() -> None:
    description = (
        "ESPARRAGO DE ROSCA CORRIDA, DE ALEACION DE ACERO, "
        "ESPECIFICACION ASTM A193/A193M GRADO B7M, "
        'DE 3/4" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
    )

    parsed = MaterialParser().parse_description(description, source_row=123)

    assert parsed.family is MaterialFamily.STUDS
    assert parsed.attributes["diametro"] == 0.75
    assert parsed.attributes["longitud"] == 5
    assert parsed.attributes["grado"] == "B7M"
    assert parsed.attributes["norma_material"].startswith("ASTM A193")
    assert "norma_tuercas" not in parsed.attributes
    assert parsed.canonical_key == (
        'ESPARRAGO|diametro=3/4"|longitud=5"|grado=B7M'
    )
    grade_evidence = next(
        item for item in parsed.evidence_spans if item.field == "grado"
    )
    assert grade_evidence.text == "B7M"
    assert description[grade_evidence.start : grade_evidence.end] == "B7M"


def test_stud_ignores_metric_value_when_imperial_measure_is_present() -> None:
    description = (
        "ESPARRAGO, DIAMETRO 19 MM, "
        'DE 3/4" DE DIAMETRO NOMINAL X 4-1/4" DE LONGITUD, '
        "ASTM A193/A193M GRADO B8M"
    )

    parsed = MaterialParser().parse_description(description)

    assert parsed.attributes["diametro"] == 0.75
    assert parsed.attributes["longitud"] == 4.25
    assert parsed.attributes["grado"] == "B8M"


@pytest.mark.parametrize(
    "prefix",
    ("INSTALACION", "MONTAJE", "RECORRIDO", "ALINEACION"),
)
def test_activity_descriptions_are_not_inventory_materials(prefix: str) -> None:
    parsed = MaterialParser().parse_description(
        f'{prefix} DE ESPARRAGO DE 3/4" X 5" DE LONGITUD ASTM A193 GRADO B7'
    )

    assert parsed.family is MaterialFamily.UNKNOWN
    assert parsed.attributes == {}
    assert "activity_description" in parsed.warnings


def test_extracts_spiral_wound_gasket_without_confusing_its_rings() -> None:
    description = (
        'EMPAQUE, DE 1-1/2" DE DIAMETRO NOMINAL, CLASE 150, '
        "TIPO ESPIROMETALICO, CON ANILLO CENTRADOR Y ANILLO INTERIOR, "
        "CARA REALZADA (-RF), ASME B16.20"
    )

    parsed = MaterialParser().parse_description(description)

    assert parsed.family is MaterialFamily.GASKETS
    assert parsed.attributes["tipo"] == "ESPIROMETALICO"
    assert parsed.attributes["anillo_centrador"] is True
    assert parsed.attributes["anillo_interior"] is True
    assert "numero_anillo" not in parsed.attributes
    assert "centrador=true" in parsed.canonical_key
    assert "interior=true" in parsed.canonical_key


def test_extracts_vcs_gasket() -> None:
    parsed = MaterialParser().parse_description(
        'KIT DE JUNTA AISLANTE, DE 1-1/2" DE DIAMETRO NOMINAL, '
        "CLASE 600, TIPO VCS, CARA REALZADA (-RF)"
    )

    assert parsed.family is MaterialFamily.GASKETS
    assert parsed.attributes["tipo"] == "VCS"
    assert parsed.attributes["clase"] == 600
    assert parsed.canonical_key.endswith("cara=RF|sistema=VCS")


def test_extracts_rtj_ring_gasket_by_ring_number() -> None:
    parsed = MaterialParser().parse_description(
        "EMPAQUE TIPO ANILLO OCTAGONAL RTJ R-102, "
        "DE ACERO INOXIDABLE, ASME B16.20"
    )

    assert parsed.family is MaterialFamily.GASKETS
    assert parsed.attributes["tipo"] == "ANILLO"
    assert parsed.attributes["numero_anillo"] == "R-102"
    assert "numero_anillo=R-102" in parsed.canonical_key


def test_extracts_pipe_schedule_thickness_and_norms() -> None:
    description = (
        'TUBO, DE 2" DE DIAMETRO NOMINAL, DE 0.218" DE ESPESOR, '
        "CEDULA (XS, 080), EXTREMOS PLANOS, DE ACERO AL CARBONO, "
        "ESPECIFICACION ASTM A106/A106M GRADO B, SIN COSTURA, "
        "DEBE CUMPLIR CON ASME B36.10"
    )

    parsed = MaterialParser().parse_description(description)

    assert parsed.family is MaterialFamily.PIPE
    assert parsed.attributes["cedula_num"] == 80
    assert parsed.attributes["cedula_alias"] == "XS"
    assert parsed.attributes["espesor"] == 0.218
    assert parsed.attributes["fabricacion"] == "SIN COSTURA"
    assert parsed.attributes["extremos"] == "PLANOS"
    assert parsed.attributes["especificacion_material"] == (
        "ASTM A106/A106M GRADO B"
    )
    assert parsed.attributes["normas_cumplimiento"] == ["ASME B36.10"]
    assert "schedule_thickness_conflict" not in parsed.warnings
    assert 'espesor=0.218"' in parsed.canonical_key


def test_pipe_canonical_key_keeps_decimal_thickness_notation() -> None:
    parsed = MaterialParser().parse_description(
        'TUBO, DE 1-1/2" DE DIAMETRO NOMINAL, '
        'DE 0.200" DE ESPESOR, CEDULA 80, '
        "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )

    assert 'espesor=0.200"' in parsed.canonical_key


def test_warns_when_verified_schedule_and_thickness_conflict() -> None:
    parsed = MaterialParser().parse_description(
        'TUBO, DE 2" DE DIAMETRO NOMINAL, DE 0.300" DE ESPESOR, '
        "CEDULA 80, DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
    )

    assert "schedule_thickness_conflict" in parsed.warnings
    assert parsed.confidence_score < 0.9


def test_rejects_structural_tubular_profile_as_pipe() -> None:
    parsed = MaterialParser().parse_description(
        'TUBO PERFIL TUBULAR DE 2", PARA ESTRUCTURA METALICA'
    )

    assert parsed.family is MaterialFamily.UNKNOWN


def test_extracts_weld_neck_flange_with_schedule() -> None:
    parsed = MaterialParser().parse_description(
        'BRIDA, CUELLO SOLDABLE (-WN), DE 2" DE DIAMETRO NOMINAL, '
        '0.218" DE ESPESOR, CEDULA (XS, 080), CLASE 150, '
        "CARA REALZADA (-RF), DE ACERO AL CARBONO, "
        "ESPECIFICACION ASTM A105/A105M, ASME B16.5"
    )

    assert parsed.family is MaterialFamily.FLANGES
    assert parsed.attributes["tipo_brida"] == "WN"
    assert parsed.attributes["cedula_num"] == 80
    assert parsed.attributes["cara"] == "RF"
    assert not any(
        warning.startswith("missing_") for warning in parsed.warnings
    )


def test_blind_flange_does_not_require_schedule() -> None:
    parsed = MaterialParser().parse_description(
        'BRIDA CIEGA (-BL), DE 3" DE DIAMETRO NOMINAL, CLASE 300, '
        "CARA DE JUNTA DE ANILLO (-RTJ), DE ACERO AL CARBONO, "
        "ASTM A105/A105M, ASME B16.5"
    )

    assert parsed.family is MaterialFamily.FLANGES
    assert parsed.attributes["tipo_brida"] == "BL"
    assert parsed.attributes["cara"] == "RTJ"
    assert "missing_cedula_o_espesor" not in parsed.warnings


def test_extracts_forged_elbow_using_class() -> None:
    parsed = MaterialParser().parse_description(
        'CODO, 90 GRADOS, DE 2" DE DIAMETRO NOMINAL, CLASE 3000, '
        "EXTREMOS INSERTO SOLDABLE, DE ACERO AL CARBONO, "
        "ESPECIFICACION ASTM A105/A105M, ASME B16.11"
    )

    assert parsed.family is MaterialFamily.ELBOWS
    assert parsed.attributes["tipo_codo"] == "90 GRADOS"
    assert parsed.attributes["clase"] == 3000
    assert parsed.attributes["extremos"] == "SW"
    assert "norma=ASME B16.11" in parsed.canonical_key


def test_extracts_butt_weld_elbow_using_schedule() -> None:
    parsed = MaterialParser().parse_description(
        'CODO, 90 GRADOS, DE 24" DE DIAMETRO NOMINAL, '
        'DE 0.375" DE ESPESOR, CEDULA (STD, 020), CON COSTURA, '
        "RADIO LARGO, EXTREMOS BISELADOS, DE ACERO AL CARBONO, "
        "ASTM A234/A234M GRADO WPB, ASME B16.9"
    )

    assert parsed.family is MaterialFamily.ELBOWS
    assert parsed.attributes["radio"] == "LARGO"
    assert parsed.attributes["cedula_num"] == 20
    assert parsed.attributes["cedula_alias"] == "STD"
    assert parsed.attributes["espesor"] == 0.375
    assert "schedule_thickness_conflict" not in parsed.warnings
    assert "norma=ASME B16.9" in parsed.canonical_key


def test_rejects_generic_accessory_list_as_elbow() -> None:
    parsed = MaterialParser().parse_description(
        "CODO, BRIDA, NIPLE, COPLE Y OTROS ACCESORIOS PARA MONTAJE"
    )

    assert parsed.family is MaterialFamily.UNKNOWN
    assert "accessory_list" in parsed.warnings


def test_reports_missing_required_fields_and_review_status() -> None:
    parsed = MaterialParser().parse_description(
        'BRIDA CIEGA, DE 2" DE DIAMETRO NOMINAL'
    )

    assert "missing_clase" in parsed.warnings
    assert "missing_material_base" in parsed.warnings
    assert "review_required" in parsed.warnings
    assert parsed.confidence_score < 0.65


def test_uses_secondary_description_only_to_complete_key_information() -> None:
    parsed = MaterialParser().parse_row(
        source_row=7,
        material_description='TUBO, DE 2" DE DIAMETRO NOMINAL',
        item_description=(
            'DE 0.218" DE ESPESOR, CEDULA (XS, 080), '
            "DE ACERO AL CARBONO, ASTM A106/A106M GRADO B"
        ),
    )

    assert parsed.source_row == 7
    assert parsed.family is MaterialFamily.PIPE
    assert parsed.attributes["cedula_num"] == 80
    assert "used_secondary_description" in parsed.warnings
    assert parsed.raw_description.startswith("TUBO")


def test_dataframe_uses_catalog_columns_and_excel_row_numbers() -> None:
    dataframe = pd.DataFrame(
        {
            "Data_DescripcionMaterial": [
                None,
                'CODO, 45 GRADOS, DE 1" DE DIAMETRO NOMINAL, CLASE 3000, '
                "DE ACERO AL CARBONO",
            ],
            "Data_DescripcionPartida": [
                'EMPAQUE, DE 3" DE DIAMETRO NOMINAL, CLASE 150, '
                "TIPO ESPIROMETALICO",
                "No debe utilizarse",
            ],
        }
    )

    parsed = MaterialParser().parse_dataframe(dataframe)

    assert [item.source_row for item in parsed] == [2, 3]
    assert parsed[0].family is MaterialFamily.GASKETS
    assert "used_secondary_description" in parsed[0].warnings
    assert parsed[1].family is MaterialFamily.ELBOWS
    assert "used_secondary_description" not in parsed[1].warnings
    assert parsed[0].to_dict()["family"] == "EMPAQUES"


def test_dataframe_requires_primary_catalog_column() -> None:
    with pytest.raises(ValueError, match="Data_DescripcionMaterial"):
        MaterialParser().parse_dataframe(pd.DataFrame({"description": ["x"]}))
