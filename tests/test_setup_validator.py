from pathlib import Path

import pandas as pd

from hermes.config import MAPPING_FIELDS
from hermes.domain.models import DataSource, HermesState, LoadedDataset
from hermes.services.setup_validator import SetupValidator


def _complete_state() -> HermesState:
    inventory = pd.DataFrame(
        {
            "description": ["Stud"],
            "code": ["A-1"],
            "available": [5],
        }
    )
    requirements = pd.DataFrame(
        {
            "udc": ["U-1"],
            "date": ["2026-06-13"],
            "description": ["Stud"],
            "required": [2],
        }
    )
    state = HermesState()
    state.set_dataset(
        LoadedDataset(DataSource.INVENTORY, Path("inventory.xlsx"), inventory)
    )
    state.set_dataset(
        LoadedDataset(DataSource.REQUIREMENTS, Path("requirements.xlsx"), requirements)
    )
    values = {
        "inventory_description": "description",
        "inventory_code": "code",
        "inventory_quantity": "available",
        "requirements_udc": "udc",
        "requirements_date": "date",
        "requirements_description": "description",
        "requirements_quantity": "required",
    }
    for key, value in values.items():
        state.set_mapping(key, value)
    return state


def test_reports_missing_files_and_mappings() -> None:
    result = SetupValidator().validate(HermesState())
    required_fields = sum(field.required for field in MAPPING_FIELDS)

    assert not result.is_valid
    assert len(result.errors) == 2 + required_fields


def test_accepts_complete_setup() -> None:
    result = SetupValidator().validate(_complete_state())

    assert result.is_valid
    assert result.errors == ()


def test_optional_backup_description_is_not_required() -> None:
    state = _complete_state()

    result = SetupValidator().validate(state)

    assert "requirements_item_description" not in state.mappings
    assert result.is_valid


def test_rejects_mapping_not_present_in_source_file() -> None:
    state = _complete_state()
    state.set_mapping("inventory_code", "missing")

    result = SetupValidator().validate(state)

    assert not result.is_valid
    assert any("ya no existe" in error for error in result.errors)
