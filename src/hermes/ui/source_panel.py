"""Reusable controls for loading and mapping one spreadsheet source."""

from __future__ import annotations

from collections.abc import Iterable
from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
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
        self.setMinimumHeight(214)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 22, 14, 12)
        layout.setSpacing(10)

        load_button = QPushButton(f"Cargar {source.display_name} (.xlsx)")
        load_button.setObjectName("loadButton")
        load_button.clicked.connect(self.load_requested.emit)
        layout.addWidget(load_button)

        self.path_label = QLabel("Ningun archivo cargado")
        self.path_label.setObjectName("filePath")
        self.path_label.setWordWrap(True)
        layout.addWidget(self.path_label)

        form_container = QWidget()
        form_container.setObjectName("mappingFormContainer")
        form = QVBoxLayout(form_container)
        form.setContentsMargins(2, 2, 6, 2)
        form.setSpacing(8)
        for field in fields:
            row = QFrame()
            row.setObjectName("mappingFieldRow")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(4)

            label = QLabel(field.label)
            label.setObjectName("mappingFieldLabel")
            label.setWordWrap(True)
            row_layout.addWidget(label)

            combo = QComboBox()
            combo.setObjectName("mappingCombo")
            combo.setEnabled(False)
            combo.setFixedHeight(32)
            combo.setMinimumWidth(180)
            combo.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
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
            row_layout.addWidget(combo)
            form.addWidget(row)
        form.addStretch()

        scroll_area = QScrollArea()
        scroll_area.setObjectName("mappingScrollArea")
        scroll_area.setMinimumHeight(74)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setWidget(form_container)
        layout.addWidget(scroll_area, stretch=1)

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

    def select_column(self, field_key: str, column: str) -> bool:
        """Select a mapped column if the selector contains it."""
        combo = self._combos.get(field_key)
        if combo is None:
            return False
        index = combo.findData(column)
        if index < 0:
            return False
        combo.setCurrentIndex(index)
        return True

    def clear_mappings(self) -> None:
        """Clear each selector and notify application state explicitly."""
        for key, combo in self._combos.items():
            empty_index = 0 if not self._required[key] and combo.count() else -1
            combo.setCurrentIndex(empty_index)
            self.mapping_changed.emit(key, "")
