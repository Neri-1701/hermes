"""Qt model adapter used to display a bounded pandas preview."""

from __future__ import annotations

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class DataFrameTableModel(QAbstractTableModel):
    """Expose the first rows of a dataframe through Qt's table model API."""

    def __init__(self, preview_limit: int, parent=None) -> None:
        """Create an empty model capped at `preview_limit` visible rows."""
        super().__init__(parent)
        self._preview_limit = preview_limit
        self._dataframe = pd.DataFrame()
        self._total_rows = 0

    @property
    def visible_rows(self) -> int:
        """Return the number of rows retained for display."""
        return len(self._dataframe)

    @property
    def total_rows(self) -> int:
        """Return the row count of the complete source dataframe."""
        return self._total_rows

    def set_dataframe(
        self,
        dataframe: pd.DataFrame,
        limit_rows: bool = True,
    ) -> None:
        """Replace the source, optionally retaining only preview rows."""
        self.beginResetModel()
        self._total_rows = len(dataframe)
        visible = (
            dataframe.head(self._preview_limit)
            if limit_rows
            else dataframe
        )
        self._dataframe = visible.copy()
        self.endResetModel()

    def clear(self) -> None:
        """Reset the model to an empty dataframe."""
        self.set_dataframe(pd.DataFrame())

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the visible row count requested by Qt views."""
        return 0 if parent.isValid() else len(self._dataframe)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the visible column count requested by Qt views."""
        return 0 if parent.isValid() else len(self._dataframe.columns)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        """Return display text for a cell, rendering missing values as empty."""
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
        """Return dataframe labels or one-based row numbers for Qt headers."""
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return str(self._dataframe.columns[section])
        return str(section + 1)
