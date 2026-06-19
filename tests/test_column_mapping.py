from pathlib import Path

from hermes.config import MAPPING_FIELDS
from hermes.services.column_mapping import ColumnMappingPreferences


def _field(key: str):
    return next(field for field in MAPPING_FIELDS if field.key == key)


def test_suggests_column_from_keywords(tmp_path: Path) -> None:
    preferences = ColumnMappingPreferences(tmp_path / "prefs.json")

    suggestion = preferences.suggest(
        _field("requirements_description"),
        (
            "UDC",
            "Cantidad requerida",
            "Descripcion larga del material",
        ),
    )

    assert suggestion == "Descripcion larga del material"


def test_remembered_column_takes_precedence(tmp_path: Path) -> None:
    path = tmp_path / "prefs.json"
    preferences = ColumnMappingPreferences(path)
    preferences.remember("inventory_code", "Clave SAP")

    restored = ColumnMappingPreferences(path)

    assert restored.suggest(
        _field("inventory_code"),
        ("Codigo generico", "Clave SAP"),
    ) == "Clave SAP"
