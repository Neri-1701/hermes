from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hermes.config import (
    APP_TITLE,
    MAPPING_FIELDS,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    PREVIEW_LIMIT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from hermes.domain.models import DataSource, HermesState
from hermes.services.excel_reader import DataLoadError, ExcelReader
from hermes.services.setup_validator import SetupValidator
from hermes.ui.dataframe_model import DataFrameTableModel
from hermes.ui.source_panel import SourcePanel


class MainWindow(QMainWindow):
    def __init__(
        self,
        excel_reader: ExcelReader | None = None,
        validator: SetupValidator | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._reader = excel_reader or ExcelReader()
        self._validator = validator or SetupValidator()
        self._state = HermesState()
        self._panels: dict[DataSource, SourcePanel] = {}

        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        self.setCentralWidget(central)

        title = QLabel("Hermes - Preparacion de datos")
        title.setObjectName("title")
        root.addWidget(title)

        subtitle = QLabel(
            "Carga archivos, asigna sus columnas y valida la configuracion antes de procesar."
        )
        root.addWidget(subtitle)

        panels_layout = QHBoxLayout()
        for source in DataSource:
            fields = [field for field in MAPPING_FIELDS if field.source == source]
            panel = SourcePanel(source, fields)
            panel.load_requested.connect(partial(self._select_dataset, source))
            panel.mapping_changed.connect(self._state.set_mapping)
            self._panels[source] = panel
            panels_layout.addWidget(panel)
        root.addLayout(panels_layout)

        actions = QHBoxLayout()
        validate_button = QPushButton("Validar configuracion")
        validate_button.clicked.connect(self.validate_setup)
        actions.addWidget(validate_button)

        clear_button = QPushButton("Limpiar vista previa")
        clear_button.clicked.connect(self.clear_preview)
        actions.addWidget(clear_button)
        actions.addStretch()

        self.status_label = QLabel("Listo")
        actions.addWidget(self.status_label)
        root.addLayout(actions)

        self.preview_model = DataFrameTableModel(PREVIEW_LIMIT, self)
        self.preview_table = QTableView()
        self.preview_table.setModel(self.preview_model)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSortingEnabled(False)
        self.preview_table.horizontalHeader().setDefaultSectionSize(180)
        root.addWidget(self.preview_table, stretch=1)

    def _select_dataset(self, source: DataSource) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Seleccionar archivo de {source.display_name}",
            "",
            "Archivos Excel (*.xlsx)",
        )
        if not path:
            return
        self.load_dataset(path, source)

    def load_dataset(self, path: str | Path, source: DataSource) -> bool:
        try:
            dataset = self._reader.read(path, source)
        except DataLoadError as exc:
            QMessageBox.critical(self, "Error de carga", str(exc))
            return False

        self._state.set_dataset(dataset)
        panel = self._panels[source]
        panel.clear_mappings()
        panel.set_dataset(dataset.path, dataset.columns)
        self.preview_model.set_dataframe(dataset.dataframe)
        self.preview_table.resizeColumnsToContents()
        self.status_label.setText(
            f"Vista de {source.display_name}: "
            f"{self.preview_model.visible_rows} de {self.preview_model.total_rows} filas"
        )
        return True

    def validate_setup(self) -> None:
        result = self._validator.validate(self._state)
        if not result.is_valid:
            QMessageBox.warning(
                self,
                "Configuracion incompleta",
                "\n".join(result.errors),
            )
            self.status_label.setText("Configuracion incompleta")
            return

        QMessageBox.information(
            self,
            "Configuracion validada",
            self._validator.build_summary(self._state),
        )
        self.status_label.setText("Configuracion validada")

    def clear_preview(self) -> None:
        self.preview_model.clear()
        self.status_label.setText("Vista previa limpia")

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background-color: #20272e;
                color: #f2f2f2;
            }
            QLabel#title {
                font-size: 22px;
                font-weight: 700;
            }
            QGroupBox {
                border: 1px solid #59636e;
                border-radius: 6px;
                font-weight: 700;
                margin-top: 10px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QPushButton {
                background-color: #3d7ea6;
                border: 0;
                border-radius: 4px;
                color: white;
                padding: 7px 12px;
            }
            QPushButton:hover {
                background-color: #4b94bd;
            }
            QComboBox, QTableView {
                background-color: #ffffff;
                color: #15191d;
                selection-background-color: #3d7ea6;
            }
            QHeaderView::section {
                background-color: #dce3e8;
                color: #15191d;
                font-weight: 700;
                padding: 5px;
            }
            """
        )
