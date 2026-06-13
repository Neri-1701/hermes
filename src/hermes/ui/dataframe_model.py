from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DataFrameTableModel(QAbstractTableModel):
    def __init__(self, preview_limit: int, parent=None) -> None:
        super().__init__(parent)
        self._preview_limit = preview_limit
        self._dataframe = pd.DataFrame()
        self._total_rows = 0

    @property
    def visible_rows(self) -> int:
        return len(self._dataframe)

    @property
    def total_rows(self) -> int:
        return self._total_rows

    def set_dataframe(self, dataframe: pd.DataFrame) -> None:
        self.beginResetModel()
        self._total_rows = len(dataframe)
        self._dataframe = dataframe.head(self._preview_limit).copy()
        self.endResetModel()

    def clear(self) -> None:
        self.set_dataframe(pd.DataFrame())

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._dataframe)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._dataframe.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None

        value = self._dataframe.iat[index.row(), index.column()]
        return "" if pd.isna(value) else str(value)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._dataframe.columns[section])
        return str(section + 1)
