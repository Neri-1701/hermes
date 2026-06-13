from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from hermes.domain.models import DataSource, LoadedDataset


class DataLoadError(ValueError):
    """Raised when an input spreadsheet cannot be used by Hermes."""


class ExcelReader:
    supported_suffixes = frozenset({".xlsx"})

    def read(self, path: str | Path, source: DataSource) -> LoadedDataset:
        file_path = Path(path).expanduser()
        self._validate_path(file_path)

        try:
            dataframe = pd.read_excel(file_path, engine="openpyxl")
        except Exception as exc:
            raise DataLoadError(
                f"No fue posible leer '{file_path.name}'. Verifica que sea un archivo Excel valido."
            ) from exc

        if dataframe.empty:
            raise DataLoadError("El archivo seleccionado no contiene filas de datos.")
        if dataframe.columns.empty:
            raise DataLoadError("El archivo seleccionado no contiene columnas.")

        normalized_columns = [str(column).strip() for column in dataframe.columns]
        duplicated_columns = {
            column
            for column, count in Counter(normalized_columns).items()
            if count > 1
        }
        if duplicated_columns:
            duplicates = ", ".join(sorted(duplicated_columns))
            raise DataLoadError(
                f"El archivo contiene encabezados duplicados despues de normalizarlos: {duplicates}."
            )

        dataframe.columns = normalized_columns
        return LoadedDataset(source=source, path=file_path.resolve(), dataframe=dataframe)

    def _validate_path(self, path: Path) -> None:
        if not path.is_file():
            raise DataLoadError(f"El archivo no existe: {path}")
        if path.suffix.lower() not in self.supported_suffixes:
            raise DataLoadError("Hermes solo admite archivos con extension .xlsx.")
