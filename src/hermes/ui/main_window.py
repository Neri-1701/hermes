"""Main PySide6 window for the Hermes data-preparation workflow."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
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
    """Coordinate spreadsheet loading, mapping, preview, and validation."""

    def __init__(
        self,
        excel_reader: ExcelReader | None = None,
        validator: SetupValidator | None = None,
        parent=None,
    ) -> None:
        """Create the window with optional service dependencies for testing."""
        super().__init__(parent)
        self._reader = excel_reader or ExcelReader()
        self._validator = validator or SetupValidator()
        self._state = HermesState()
        self._panels: dict[DataSource, SourcePanel] = {}
        self._dark_mode = False

        self.setWindowTitle(APP_TITLE)
        self.resize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.setMinimumSize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self._build_menu()
        self._build_ui()
        self._apply_styles()

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()
        menu_bar.setNativeMenuBar(False)
        settings_menu = menu_bar.addMenu("Configuracion")
        settings_menu.setObjectName("settingsMenu")
        self.dark_mode_action = QAction("Modo oscuro", self)
        self.dark_mode_action.setObjectName("darkModeAction")
        self.dark_mode_action.setCheckable(True)
        self.dark_mode_action.toggled.connect(self._set_dark_mode)
        settings_menu.addAction(self.dark_mode_action)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("centralWidget")
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 28)
        root.setSpacing(18)
        self.setCentralWidget(central)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(22, 18, 22, 18)
        header_layout.setSpacing(4)

        eyebrow = QLabel("GESTION DE MATERIALES")
        eyebrow.setObjectName("eyebrow")
        header_layout.addWidget(eyebrow)

        title = QLabel("Preparacion de datos")
        title.setObjectName("title")
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Carga los archivos, relaciona sus columnas y revisa la configuracion "
            "antes de procesar."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(16)
        for source in DataSource:
            fields = [field for field in MAPPING_FIELDS if field.source == source]
            panel = SourcePanel(source, fields)
            panel.load_requested.connect(partial(self._select_dataset, source))
            panel.mapping_changed.connect(self._state.set_mapping)
            self._panels[source] = panel
            panels_layout.addWidget(panel)
        root.addLayout(panels_layout)

        preview_card = QFrame()
        preview_card.setObjectName("previewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        preview_header = QFrame()
        preview_header.setObjectName("previewHeader")
        preview_header_layout = QHBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(18, 14, 18, 14)
        preview_header_layout.setSpacing(10)

        preview_copy = QVBoxLayout()
        preview_copy.setSpacing(2)
        preview_title = QLabel("Vista previa")
        preview_title.setObjectName("sectionTitle")
        preview_copy.addWidget(preview_title)

        self.status_label = QLabel("Sin datos cargados")
        self.status_label.setObjectName("status")
        preview_copy.addWidget(self.status_label)
        preview_header_layout.addLayout(preview_copy)
        preview_header_layout.addStretch()

        preview_source_label = QLabel("Mostrar archivo:")
        preview_source_label.setObjectName("previewSourceLabel")
        preview_header_layout.addWidget(preview_source_label)

        self.preview_source_combo = QComboBox()
        self.preview_source_combo.setObjectName("previewSource")
        self.preview_source_combo.setEnabled(False)
        self.preview_source_combo.setMinimumWidth(160)
        self.preview_source_combo.currentIndexChanged.connect(
            self._change_preview_source
        )
        preview_header_layout.addWidget(self.preview_source_combo)

        validate_button = QPushButton("Validar configuracion")
        validate_button.setObjectName("primaryButton")
        validate_button.clicked.connect(self.validate_setup)
        preview_header_layout.addWidget(validate_button)

        clear_button = QPushButton("Limpiar vista previa")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(self.clear_preview)
        preview_header_layout.addWidget(clear_button)
        preview_layout.addWidget(preview_header)

        self.preview_model = DataFrameTableModel(PREVIEW_LIMIT, self)
        self.preview_table = QTableView()
        self.preview_table.setObjectName("previewTable")
        self.preview_table.setModel(self.preview_model)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSortingEnabled(False)
        self.preview_table.setShowGrid(False)
        self.preview_table.setCornerButtonEnabled(False)
        self.preview_table.horizontalHeader().setDefaultSectionSize(180)
        self.preview_table.verticalHeader().setDefaultSectionSize(34)
        preview_layout.addWidget(self.preview_table, stretch=1)
        root.addWidget(preview_card, stretch=1)

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
        """Load one spreadsheet source and make it the active preview.

        Returns `True` after a successful load. Validation failures are shown
        to the user and return `False` without replacing application state.
        """
        try:
            dataset = self._reader.read(path, source)
        except DataLoadError as exc:
            QMessageBox.critical(self, "Error de carga", str(exc))
            return False

        self._state.set_dataset(dataset)
        panel = self._panels[source]
        panel.clear_mappings()
        panel.set_dataset(dataset.path, dataset.columns)
        self._add_preview_source(source)
        self._select_preview_source(source)
        return True

    def _add_preview_source(self, source: DataSource) -> None:
        if self.preview_source_combo.findData(source.value) < 0:
            self.preview_source_combo.addItem(
                source.display_name.capitalize(),
                source.value,
            )
        self.preview_source_combo.setEnabled(True)

    def _select_preview_source(self, source: DataSource) -> None:
        index = self.preview_source_combo.findData(source.value)
        # The preview is refreshed once below; suppress the combo's duplicate event.
        self.preview_source_combo.blockSignals(True)
        self.preview_source_combo.setCurrentIndex(index)
        self.preview_source_combo.blockSignals(False)
        self._show_preview(source)

    def _change_preview_source(self, index: int) -> None:
        source_value = self.preview_source_combo.itemData(index)
        if source_value:
            self._show_preview(DataSource(source_value))

    def _show_preview(self, source: DataSource) -> None:
        dataset = self._state.dataset_for(source)
        if dataset is None:
            return

        self.preview_model.set_dataframe(dataset.dataframe)
        self.preview_table.resizeColumnsToContents()
        self.status_label.setText(
            f"Vista de {source.display_name}: "
            f"{self.preview_model.visible_rows} de {self.preview_model.total_rows} filas"
        )

    def validate_setup(self) -> None:
        """Validate the current setup and present all resulting feedback."""
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
        """Clear only the table view while preserving loaded datasets."""
        self.preview_model.clear()
        self.status_label.setText("Vista previa limpia")

    def _set_dark_mode(self, enabled: bool) -> None:
        self._dark_mode = enabled
        self._apply_styles()

    def _apply_styles(self) -> None:
        light_styles = """
            QMainWindow, QWidget#centralWidget {
                background-color: #f3f5f7;
                color: #172033;
                font-size: 13px;
            }
            QMenuBar {
                background-color: #ffffff;
                border-bottom: 1px solid #e3e7ed;
                color: #263247;
                padding: 3px 6px;
            }
            QMenuBar::item {
                background-color: transparent;
                border-radius: 5px;
                padding: 6px 10px;
            }
            QMenuBar::item:selected {
                background-color: #eef2ff;
                color: #3348a8;
            }
            QMenu {
                background-color: #ffffff;
                border: 1px solid #dce1e8;
                color: #263247;
                padding: 5px;
            }
            QMenu::item {
                border-radius: 5px;
                padding: 7px 28px 7px 10px;
            }
            QMenu::item:selected {
                background-color: #e8ecff;
                color: #263247;
            }
            QMenu::indicator {
                width: 14px;
                height: 14px;
            }
            QFrame#header {
                background-color: #ffffff;
                border: 1px solid #e3e7ed;
                border-radius: 12px;
            }
            QLabel#eyebrow {
                color: #65758b;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            }
            QLabel#title {
                color: #172033;
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#subtitle {
                color: #65758b;
                font-size: 13px;
            }
            QGroupBox {
                background-color: #ffffff;
                border: 1px solid #e3e7ed;
                border-radius: 12px;
                color: #263247;
                font-size: 14px;
                font-weight: 700;
                margin-top: 12px;
                padding: 18px 14px 14px 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                padding: 0 6px;
            }
            QLabel#filePath {
                color: #748196;
                font-size: 12px;
                padding: 2px 1px 8px 1px;
            }
            QPushButton {
                background-color: #eef2ff;
                border: 1px solid #d9e0ff;
                border-radius: 7px;
                color: #3348a8;
                font-weight: 600;
                min-height: 18px;
                padding: 8px 14px;
            }
            QPushButton:hover {
                background-color: #e1e7ff;
                border-color: #bdc9ff;
            }
            QPushButton:pressed {
                background-color: #d5ddff;
            }
            QPushButton#primaryButton {
                background-color: #4056c7;
                border-color: #4056c7;
                color: #ffffff;
            }
            QPushButton#primaryButton:hover {
                background-color: #3549ae;
                border-color: #3549ae;
            }
            QPushButton#secondaryButton {
                background-color: #ffffff;
                border-color: #dce1e8;
                color: #4d5b70;
            }
            QPushButton#secondaryButton:hover {
                background-color: #f7f8fa;
                border-color: #cbd2dc;
            }
            QComboBox {
                background-color: #fbfcfd;
                border: 1px solid #dce1e8;
                border-radius: 7px;
                color: #263247;
                min-height: 20px;
                padding: 6px 10px;
            }
            QComboBox:hover {
                border-color: #aeb9c8;
            }
            QComboBox:focus {
                background-color: #ffffff;
                border: 1px solid #6377d8;
            }
            QComboBox:disabled {
                background-color: #f1f3f5;
                color: #9aa4b2;
            }
            QComboBox::drop-down {
                border: 0;
                width: 28px;
            }
            QComboBox QAbstractItemView {
                background-color: #ffffff;
                border: 1px solid #dce1e8;
                color: #263247;
                outline: 0;
                selection-background-color: #e8ecff;
                selection-color: #263247;
            }
            QFrame#previewCard {
                background-color: #ffffff;
                border: 1px solid #e3e7ed;
                border-radius: 12px;
            }
            QFrame#previewHeader {
                background-color: transparent;
                border: 0;
                border-bottom: 1px solid #e8ebef;
            }
            QLabel#sectionTitle {
                color: #263247;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#status {
                color: #748196;
                font-size: 12px;
            }
            QLabel#previewSourceLabel {
                color: #65758b;
                font-size: 12px;
                font-weight: 600;
            }
            QComboBox#previewSource {
                background-color: #ffffff;
            }
            QTableView#previewTable {
                background-color: #ffffff;
                alternate-background-color: #f8f9fb;
                border: 0;
                border-bottom-left-radius: 12px;
                border-bottom-right-radius: 12px;
                color: #263247;
                outline: 0;
                selection-background-color: #e3e8ff;
                selection-color: #1f2d5c;
            }
            QHeaderView::section {
                background-color: #f2f4f7;
                border: 0;
                border-bottom: 1px solid #e1e5ea;
                border-right: 1px solid #e8ebef;
                color: #526176;
                font-weight: 700;
                padding: 8px 10px;
            }
            QTableCornerButton::section {
                background-color: #f2f4f7;
                border: 0;
            }
            QScrollBar:vertical {
                background-color: transparent;
                margin: 4px;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background-color: #cbd2dc;
                border-radius: 4px;
                min-height: 28px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background-color: transparent;
                height: 10px;
                margin: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #cbd2dc;
                border-radius: 4px;
                min-width: 28px;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }
            """
        dark_styles = """
            QMainWindow, QWidget#centralWidget {
                background-color: #111827;
                color: #e5e7eb;
            }
            QMenuBar {
                background-color: #182235;
                border-bottom-color: #334155;
                color: #e5e7eb;
            }
            QMenuBar::item:selected {
                background-color: #273553;
                color: #c7d2fe;
            }
            QMenu {
                background-color: #182235;
                border-color: #3b4960;
                color: #e5e7eb;
            }
            QMenu::item:selected {
                background-color: #35456a;
                color: #ffffff;
            }
            QFrame#header,
            QGroupBox,
            QFrame#previewCard {
                background-color: #182235;
                border-color: #334155;
            }
            QLabel#eyebrow,
            QLabel#subtitle,
            QLabel#filePath,
            QLabel#status,
            QLabel#previewSourceLabel {
                color: #a8b3c5;
            }
            QLabel#title,
            QLabel#sectionTitle,
            QGroupBox {
                color: #f1f5f9;
            }
            QPushButton {
                background-color: #273553;
                border-color: #405379;
                color: #c7d2fe;
            }
            QPushButton:hover {
                background-color: #35456a;
                border-color: #5b6f99;
            }
            QPushButton:pressed {
                background-color: #202c45;
            }
            QPushButton#primaryButton {
                background-color: #596fd6;
                border-color: #596fd6;
                color: #ffffff;
            }
            QPushButton#primaryButton:hover {
                background-color: #6c80df;
                border-color: #6c80df;
            }
            QPushButton#secondaryButton {
                background-color: #1f2b3f;
                border-color: #40506a;
                color: #d5dbea;
            }
            QPushButton#secondaryButton:hover {
                background-color: #2b3951;
                border-color: #53647f;
            }
            QComboBox,
            QComboBox#previewSource {
                background-color: #1f2b3f;
                border-color: #40506a;
                color: #e5e7eb;
            }
            QComboBox:hover {
                border-color: #7183a2;
            }
            QComboBox:focus {
                background-color: #243149;
                border-color: #8192e8;
            }
            QComboBox:disabled {
                background-color: #172133;
                color: #6f7d92;
            }
            QComboBox QAbstractItemView {
                background-color: #1f2b3f;
                border-color: #40506a;
                color: #e5e7eb;
                selection-background-color: #35456a;
                selection-color: #ffffff;
            }
            QFrame#previewHeader {
                border-bottom-color: #334155;
            }
            QTableView#previewTable {
                background-color: #182235;
                alternate-background-color: #1d293c;
                color: #e5e7eb;
                selection-background-color: #35456a;
                selection-color: #ffffff;
            }
            QHeaderView::section,
            QTableCornerButton::section {
                background-color: #202c40;
                border-bottom-color: #40506a;
                border-right-color: #334155;
                color: #cbd5e1;
            }
            QScrollBar::handle:vertical,
            QScrollBar::handle:horizontal {
                background-color: #53627a;
            }
            """
        self.setStyleSheet(
            light_styles + dark_styles if self._dark_mode else light_styles
        )
