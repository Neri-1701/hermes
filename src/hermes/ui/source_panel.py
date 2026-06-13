from __future__ import annotations

from collections.abc import Iterable
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
    load_requested = Signal()
    mapping_changed = Signal(str, str)

    def __init__(
        self,
        source: DataSource,
        fields: Iterable[MappingField],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.source = source
        self._combos: dict[str, QComboBox] = {}

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
            combo.setPlaceholderText("Selecciona una columna")
            combo.currentTextChanged.connect(
                lambda value, key=field.key: self.mapping_changed.emit(key, value)
            )
            self._combos[field.key] = combo
            form.addRow(field.label, combo)
        layout.addLayout(form)
        layout.addStretch()

    def set_dataset(self, path: Path, columns: Iterable[str]) -> None:
        self.path_label.setText(str(path))
        values = list(columns)
        for combo in self._combos.values():
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(values)
            combo.setCurrentIndex(-1)
            combo.setEnabled(True)
            combo.blockSignals(False)

    def clear_mappings(self) -> None:
        for key, combo in self._combos.items():
            combo.setCurrentIndex(-1)
            self.mapping_changed.emit(key, "")
