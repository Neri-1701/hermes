from pathlib import Path

import pandas as pd

from hermes.application import create_application
from hermes.config import APP_TITLE
from hermes.domain.models import DataSource
from hermes.domain.reconciliation import ReconciliationStatus
from hermes.services.column_mapping import ColumnMappingPreferences
from hermes.ui.main_window import MainWindow
from PySide6.QtWidgets import QFileDialog, QMessageBox


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
    assert "#26344a" not in window.reconciliation_dashboard.styleSheet()

    window.dark_mode_action.setChecked(True)

    assert window.dark_mode_action.isChecked()
    assert "#111827" in window.styleSheet()
    assert "#26344a" in window.reconciliation_dashboard.styleSheet()

    window.dark_mode_action.setChecked(False)

    assert window.styleSheet() == light_styles
    assert "#26344a" not in window.reconciliation_dashboard.styleSheet()

    window.close()


def test_main_window_can_hide_configuration_panel() -> None:
    create_application(["hermes-test"])
    window = MainWindow()

    assert not window.configuration_panel.isHidden()
    assert window.configuration_toggle_button.text() == "Ocultar config."

    window.configuration_toggle_button.click()

    assert window.configuration_panel.isHidden()
    assert window.configuration_toggle_button.text() == "Mostrar config."

    window.configuration_toggle_button.click()

    assert not window.configuration_panel.isHidden()
    assert window.configuration_toggle_button.text() == "Ocultar config."

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


def test_main_window_auto_selects_likely_columns(tmp_path: Path) -> None:
    path = tmp_path / "inventory.xlsx"
    pd.DataFrame(
        {
            "Codigo Material": ["A-1"],
            "Descripcion larga material": ["Stud"],
            "Cantidad disponible": [5],
        }
    ).to_excel(path, index=False)
    create_application(["hermes-test"])
    window = MainWindow(
        mapping_preferences=ColumnMappingPreferences(tmp_path / "prefs.json")
    )

    window.load_dataset(path, DataSource.INVENTORY)

    assert window._state.mappings["inventory_code"] == "Codigo Material"
    assert window._state.mappings["inventory_description"] == (
        "Descripcion larga material"
    )
    assert window._state.mappings["inventory_quantity"] == "Cantidad disponible"

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


def test_main_window_quick_search_needs_only_inventory(tmp_path: Path) -> None:
    description = (
        "ESPARRAGO ASTM A193/A193M GRADO B7, "
        'DE 3/4" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
    )
    inventory_path = tmp_path / "inventory.xlsx"
    pd.DataFrame(
        {
            "description": [description],
            "code": ["E-1"],
            "available": [5],
        }
    ).to_excel(inventory_path, index=False)
    create_application(["hermes-test"])
    window = MainWindow()
    window.load_dataset(inventory_path, DataSource.INVENTORY)
    for key, value in {
        "inventory_description": "description",
        "inventory_code": "code",
        "inventory_quantity": "available",
    }.items():
        window._set_mapping(key, value)

    window.search_input.setText(description)
    window.search_button.click()

    assert window._state.dataset_for(DataSource.REQUIREMENTS) is None
    assert window.preview_source_combo.currentData() == (
        window.QUICK_SEARCH_RESULTS
    )
    assert window.preview_model.rowCount() == 1
    assert "1 coincidencias" in window.status_label.text()
    assert window.preview_source_combo.count() == 2
    assert not window.export_report_button.isEnabled()

    window.close()


def test_main_window_exports_segmentation_report(
    tmp_path: Path,
    monkeypatch,
) -> None:
    description = (
        "ESPARRAGO ASTM A193/A193M GRADO B7, "
        'DE 3/4" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
    )
    inventory_path = tmp_path / "inventory.xlsx"
    requirements_path = tmp_path / "requirements.xlsx"
    report_path = tmp_path / "segmentation_report.xlsx"
    pd.DataFrame(
        {
            "description": [description],
            "code": ["E-1"],
            "available": [5],
        }
    ).to_excel(inventory_path, index=False)
    pd.DataFrame(
        {
            "udc": ["U-1"],
            "date": ["2026-06-15"],
            "description": [description],
            "required": [2],
        }
    ).to_excel(requirements_path, index=False)
    create_application(["hermes-test"])
    window = MainWindow()
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(report_path), "Archivos Excel (*.xlsx)"),
    )
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    window.load_dataset(inventory_path, DataSource.INVENTORY)
    window.load_dataset(requirements_path, DataSource.REQUIREMENTS)
    mappings = {
        "inventory_description": "description",
        "inventory_code": "code",
        "inventory_quantity": "available",
        "requirements_description": "description",
        "requirements_quantity": "required",
    }
    for key, value in mappings.items():
        window._set_mapping(key, value)

    assert not window.export_report_button.isEnabled()
    assert window.run_reconciliation()
    assert window.export_report_button.isEnabled()
    assert window.export_reconciliation_report()

    sheets = pd.read_excel(report_path, sheet_name=None)
    assert set(sheets) == {"Requerimientos"}
    assert sheets["Requerimientos"].loc[0, "udc"] == "U-1"
    assert sheets["Requerimientos"].loc[0, "codigo(s) asignado(s)"] == "E-1"
    assert sheets["Requerimientos"].loc[0, "cantidad_total_asignada"] == 2

    window.close()


def test_main_window_segments_and_searches_inventory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    description = (
        "ESPARRAGO ASTM A193/A193M GRADO B7, "
        'DE 3/4" DE DIAMETRO NOMINAL X 5" DE LONGITUD'
    )
    inventory_path = tmp_path / "inventory.xlsx"
    requirements_path = tmp_path / "requirements.xlsx"
    pd.DataFrame(
        {
            "description": [description],
            "code": ["E-1"],
            "available": [5],
        }
    ).to_excel(inventory_path, index=False)
    pd.DataFrame(
        {
            "udc": ["U-1"],
            "date": ["2026-06-15"],
            "description": [description],
            "required": [2],
        }
    ).to_excel(requirements_path, index=False)
    create_application(["hermes-test"])
    window = MainWindow()
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args, **kwargs: QMessageBox.StandardButton.Ok,
    )

    window.load_dataset(inventory_path, DataSource.INVENTORY)
    window.load_dataset(requirements_path, DataSource.REQUIREMENTS)
    mappings = {
        "inventory_description": "description",
        "inventory_code": "code",
        "inventory_quantity": "available",
        "requirements_description": "description",
        "requirements_quantity": "required",
    }
    for key, value in mappings.items():
        window._set_mapping(key, value)

    window.process_button.click()

    report = window._state.reconciliation_report
    assert report is not None
    assert report.matches.iloc[0]["estado"] == (
        ReconciliationStatus.COVERED.value
    )
    assert window.preview_source_combo.count() == 7
    assert window.preview_source_combo.currentData() == window.BI_DASHBOARD
    assert window.preview_stack.currentWidget() == window.reconciliation_dashboard
    assert "Resumen BI" in window.status_label.text()

    matches_index = window.preview_source_combo.findData(window.MATCH_RESULTS)
    window.preview_source_combo.setCurrentIndex(matches_index)

    assert window.preview_stack.currentWidget() == window.preview_table
    assert window.preview_model.rowCount() == 1
    assert "Cruce de inventario" in window.status_label.text()

    requirement_index = window.preview_source_combo.findData(
        window.REQUIREMENT_SEGMENTATION
    )
    window.preview_source_combo.setCurrentIndex(requirement_index)

    assert "Requerimientos segmentados" in window.status_label.text()
    assert window.preview_model.rowCount() == 1

    window._set_mapping("requirements_quantity", "")

    assert window._state.reconciliation_report is None
    assert window.preview_source_combo.count() == 2

    window.close()
