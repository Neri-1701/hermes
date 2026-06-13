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
