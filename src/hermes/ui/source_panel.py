"""Reusable controls for loading and mapping one spreadsheet source."""

from __future__ import annotations

from collections.abc import Iterable
from functools import partial
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from hermes.config import MappingField
from hermes.domain.models import DataSource


class SourcePanel(QGroupBox):
    """Panel that emits file-load requests and field mapping changes."""

    load_requested = Signal()
    mapping_changed = Signal(str, str)

    def __init__(
        self,
        source: DataSource,
        fields: Iterable[MappingField],
        parent=None,
    ) -> None:
        """Build controls for the mapping fields associated with `source`."""
        super().__init__(parent)
        self.source = source
        self._combos: dict[str, QComboBox] = {}
        self._required: dict[str, bool] = {}

        self.setTitle(f"Archivo de {source.display_name}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(10)

        load_button = QPushButton(f"Cargar {source.display_name} (.xlsx)")
        load_button.setObjectName("loadButton")
        load_button.clicked.connect(self.load_requested.emit)
        layout.addWidget(load_button)

        self.path_label = QLabel("Ningun archivo cargado")
        self.path_label.setObjectName("filePath")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        form = QFormLayout()
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)
        for field in fields:
            combo = QComboBox()
            combo.setEnabled(False)
            combo.setPlaceholderText(
                "Selecciona una columna"
                if field.required
                else "Sin columna de respaldo"
            )
            combo.currentIndexChanged.connect(
                partial(self._emit_mapping, field.key, combo)
            )
            self._combos[field.key] = combo
            self._required[field.key] = field.required
            form.addRow(field.label, combo)
        layout.addLayout(form)
        layout.addStretch()

    def _emit_mapping(
        self,
        key: str,
        combo: QComboBox,
        _index: int,
    ) -> None:
        self.mapping_changed.emit(key, combo.currentData() or "")

    def set_dataset(self, path: Path, columns: Iterable[str]) -> None:
        """Show a loaded path and repopulate every mapping selector."""
        self.path_label.setText(str(path))
        values = list(columns)
        for key, combo in self._combos.items():
            # Repopulating options must not create mappings on the user's behalf.
            combo.blockSignals(True)
            combo.clear()
            if not self._required[key]:
                combo.addItem("Sin columna de respaldo", "")
            for value in values:
                combo.addItem(value, value)
            combo.setCurrentIndex(0 if not self._required[key] else -1)
            combo.setEnabled(True)
            combo.blockSignals(False)

    def clear_mappings(self) -> None:
        """Clear each selector and notify application state explicitly."""
        for key, combo in self._combos.items():
            empty_index = 0 if not self._required[key] and combo.count() else -1
            combo.setCurrentIndex(empty_index)
            self.mapping_changed.emit(key, "")
