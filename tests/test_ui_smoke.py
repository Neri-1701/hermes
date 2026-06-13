from pathlib import Path

import pandas as pd

from hermes.application import create_application
from hermes.config import APP_TITLE
from hermes.domain.models import DataSource
from hermes.ui.main_window import MainWindow


def test_main_window_can_be_created() -> None:
    app = create_application(["hermes-test"])
    window = MainWindow()

    assert app.applicationName() == APP_TITLE
    assert window.windowTitle() == APP_TITLE

    window.close()


def test_main_window_toggles_dark_mode() -> None:
    create_application(["hermes-test"])
    window = MainWindow()
    light_styles = window.styleSheet()

    assert not window.menuBar().isNativeMenuBar()
    assert window.menuBar().actions()[0].text() == "Configuracion"
    assert window.dark_mode_action.isCheckable()
    assert not window.dark_mode_action.isChecked()
    assert "#111827" not in light_styles

    window.dark_mode_action.setChecked(True)

    assert window.dark_mode_action.isChecked()
    assert "#111827" in window.styleSheet()

    window.dark_mode_action.setChecked(False)

    assert window.styleSheet() == light_styles

    window.close()


def test_main_window_loads_spreadsheet(tmp_path: Path) -> None:
    path = tmp_path / "inventory.xlsx"
    pd.DataFrame({"code": ["A-1"], "quantity": [5]}).to_excel(path, index=False)
    create_application(["hermes-test"])
    window = MainWindow()

    loaded = window.load_dataset(path, DataSource.INVENTORY)

    assert loaded
    assert window.preview_model.rowCount() == 1
    assert window.preview_model.columnCount() == 2
    assert "1 de 1 filas" in window.status_label.text()

    window.close()


def test_main_window_switches_between_loaded_previews(tmp_path: Path) -> None:
    inventory_path = tmp_path / "inventory.xlsx"
    requirements_path = tmp_path / "requirements.xlsx"
    pd.DataFrame({"inventory_code": ["A-1"]}).to_excel(
        inventory_path,
        index=False,
    )
    pd.DataFrame(
        {
            "requirement_code": ["R-1", "R-2"],
            "quantity": [5, 8],
        }
    ).to_excel(requirements_path, index=False)
    create_application(["hermes-test"])
    window = MainWindow()

    window.load_dataset(inventory_path, DataSource.INVENTORY)
    window.load_dataset(requirements_path, DataSource.REQUIREMENTS)

    assert window.preview_source_combo.count() == 2
    assert window.preview_model.rowCount() == 2
    assert window.preview_model.columnCount() == 2
    assert "requerimientos" in window.status_label.text()

    inventory_index = window.preview_source_combo.findData(
        DataSource.INVENTORY.value
    )
    window.preview_source_combo.setCurrentIndex(inventory_index)

    assert window.preview_model.rowCount() == 1
    assert window.preview_model.columnCount() == 1
    assert (
        window.preview_model.headerData(
            0,
            window.preview_table.horizontalHeader().orientation(),
        )
        == "inventory_code"
    )
    assert "inventario" in window.status_label.text()

    window.close()
