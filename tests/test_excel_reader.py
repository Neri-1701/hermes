from pathlib import Path

import pandas as pd
import pytest

from hermes.domain.models import DataSource
from hermes.services.excel_reader import DataLoadError, ExcelReader


def test_reads_xlsx_file(tmp_path: Path) -> None:
    path = tmp_path / "inventory.xlsx"
    pd.DataFrame({" code ": ["A-1"], "quantity": [5]}).to_excel(path, index=False)

    dataset = ExcelReader().read(path, DataSource.INVENTORY)

    assert dataset.path == path.resolve()
    assert dataset.columns == ("code", "quantity")
    assert dataset.dataframe.iloc[0]["quantity"] == 5


def test_rejects_empty_spreadsheet(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    pd.DataFrame(columns=["code"]).to_excel(path, index=False)

    with pytest.raises(DataLoadError, match="no contiene filas"):
        ExcelReader().read(path, DataSource.INVENTORY)


def test_rejects_unsupported_file_type(tmp_path: Path) -> None:
    path = tmp_path / "inventory.csv"
    path.write_text("code,quantity\nA-1,5\n", encoding="utf-8")

    with pytest.raises(DataLoadError, match=".xlsx"):
        ExcelReader().read(path, DataSource.INVENTORY)


def test_rejects_headers_duplicated_after_normalization(tmp_path: Path) -> None:
    path = tmp_path / "duplicates.xlsx"
    pd.DataFrame([["A-1", 5]], columns=[" code ", "code"]).to_excel(path, index=False)

    with pytest.raises(DataLoadError, match="encabezados duplicados"):
        ExcelReader().read(path, DataSource.INVENTORY)
