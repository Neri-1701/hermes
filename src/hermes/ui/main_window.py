"""Main PySide6 window for the Hermes data-preparation workflow."""

from __future__ import annotations

from functools import partial
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hermes import __version__
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
from hermes.services.column_mapping import ColumnMappingPreferences
from hermes.services.excel_reader import DataLoadError, ExcelReader
from hermes.services.reconciliation import (
    ReconciliationError,
    ReconciliationService,
)
from hermes.services.setup_validator import SetupValidator
from hermes.ui.dataframe_model import DataFrameTableModel
from hermes.ui.reconciliation_dashboard import ReconciliationDashboard
from hermes.ui.source_panel import SourcePanel


class MainWindow(QMainWindow):
    """Coordinate spreadsheet loading, mapping, preview, and validation."""

    MATCH_RESULTS = "result:matches"
    USER_REPORT = "result:user_report"
    REQUIREMENT_SEGMENTATION = "result:requirements"
    INVENTORY_SEGMENTATION = "result:inventory"
    QUICK_SEARCH_RESULTS = "result:search"
    BI_DASHBOARD = "result:bi_dashboard"

    def __init__(
        self,
        excel_reader: ExcelReader | None = None,
        validator: SetupValidator | None = None,
        reconciler: ReconciliationService | None = None,
        mapping_preferences: ColumnMappingPreferences | None = None,
        parent=None,
    ) -> None:
        """Create the window with optional service dependencies for testing."""
        super().__init__(parent)
        self._reader = excel_reader or ExcelReader()
        self._validator = validator or SetupValidator()
        self._reconciler = reconciler or ReconciliationService()
        self._mapping_preferences = (
            mapping_preferences or ColumnMappingPreferences()
        )
        self._state = HermesState()
        self._panels: dict[DataSource, SourcePanel] = {}
        self._search_results = None
        self._configuration_splitter_sizes = [260, 420]
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
        root.setContentsMargins(24, 18, 24, 20)
        root.setSpacing(12)
        self.setCentralWidget(central)

        header = QFrame()
        header.setObjectName("header")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 12, 18, 12)
        header_layout.setSpacing(3)

        eyebrow = QLabel("GESTION DE MATERIALES")
        eyebrow.setObjectName("eyebrow")
        header_layout.addWidget(eyebrow)

        title = QLabel("HERMES: Segmentacion y cruce de materiales")
        title.setObjectName("title")
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Carga los archivos, relaciona sus columnas y ejecuta la segmentacion "
            "para localizar inventario compatible."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)
        root.addWidget(header)

        self.workspace_splitter = QSplitter(Qt.Orientation.Vertical)
        self.workspace_splitter.setObjectName("workspaceSplitter")
        self.workspace_splitter.setChildrenCollapsible(False)

        self.configuration_panel = QFrame()
        self.configuration_panel.setObjectName("configurationPanel")
        configuration_layout = QVBoxLayout(self.configuration_panel)
        configuration_layout.setContentsMargins(0, 0, 0, 0)
        configuration_layout.setSpacing(12)

        panels_layout = QHBoxLayout()
        panels_layout.setSpacing(16)
        for source in DataSource:
            fields = [field for field in MAPPING_FIELDS if field.source == source]
            panel = SourcePanel(source, fields)
            panel.load_requested.connect(partial(self._select_dataset, source))
            panel.mapping_changed.connect(self._set_mapping)
            self._panels[source] = panel
            panels_layout.addWidget(panel, stretch=1)
        configuration_layout.addLayout(panels_layout, stretch=1)

        search_card = QFrame()
        search_card.setObjectName("quickSearchCard")
        search_layout = QHBoxLayout(search_card)
        search_layout.setContentsMargins(16, 12, 16, 12)
        search_layout.setSpacing(10)

        search_label = QLabel("Busqueda rapida:")
        search_label.setObjectName("quickSearchLabel")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("quickSearchInput")
        self.search_input.setPlaceholderText(
            'Ejemplo: TUBO DE 2" CEDULA 80 DE ACERO AL CARBONO'
        )
        self.search_input.returnPressed.connect(self.run_quick_search)
        search_layout.addWidget(self.search_input, stretch=1)

        self.search_button = QPushButton("Buscar en inventario")
        self.search_button.setObjectName("secondaryButton")
        self.search_button.clicked.connect(self.run_quick_search)
        search_layout.addWidget(self.search_button)

        configuration_layout.addWidget(search_card)
        self.workspace_splitter.addWidget(self.configuration_panel)

        preview_card = QFrame()
        preview_card.setObjectName("previewCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        preview_header = QFrame()
        preview_header.setObjectName("previewHeader")
        preview_header_layout = QVBoxLayout(preview_header)
        preview_header_layout.setContentsMargins(18, 14, 18, 14)
        preview_header_layout.setSpacing(8)

        preview_title_row = QHBoxLayout()
        preview_title_row.setSpacing(10)

        preview_copy = QVBoxLayout()
        preview_copy.setSpacing(2)
        preview_title = QLabel("Datos y resultados")
        preview_title.setObjectName("sectionTitle")
        preview_copy.addWidget(preview_title)

        self.status_label = QLabel("Sin datos cargados")
        self.status_label.setObjectName("status")
        preview_copy.addWidget(self.status_label)
        preview_title_row.addLayout(preview_copy)
        preview_title_row.addStretch()

        self.configuration_toggle_button = QPushButton("Ocultar config.")
        self.configuration_toggle_button.setObjectName("secondaryButton")
        self.configuration_toggle_button.clicked.connect(
            self._toggle_configuration_panel
        )
        preview_title_row.addWidget(self.configuration_toggle_button)
        preview_header_layout.addLayout(preview_title_row)

        preview_controls_row = QHBoxLayout()
        preview_controls_row.setSpacing(10)
        preview_controls_row.addStretch()

        preview_source_label = QLabel("Mostrar vista:")
        preview_source_label.setObjectName("previewSourceLabel")
        preview_controls_row.addWidget(preview_source_label)

        self.preview_source_combo = QComboBox()
        self.preview_source_combo.setObjectName("previewSource")
        self.preview_source_combo.setEnabled(False)
        self.preview_source_combo.setMinimumWidth(160)
        self.preview_source_combo.currentIndexChanged.connect(
            self._change_preview_source
        )
        preview_controls_row.addWidget(self.preview_source_combo)

        validate_button = QPushButton("Validar")
        validate_button.setObjectName("secondaryButton")
        validate_button.clicked.connect(self.validate_setup)
        preview_controls_row.addWidget(validate_button)

        self.process_button = QPushButton("Segmentar")
        self.process_button.setObjectName("primaryButton")
        self.process_button.clicked.connect(self.run_reconciliation)
        preview_controls_row.addWidget(self.process_button)

        self.export_report_button = QPushButton("Exportar reporte")
        self.export_report_button.setObjectName("secondaryButton")
        self.export_report_button.setEnabled(False)
        self.export_report_button.clicked.connect(
            self.export_reconciliation_report
        )
        preview_controls_row.addWidget(self.export_report_button)

        clear_button = QPushButton("Limpiar")
        clear_button.setObjectName("secondaryButton")
        clear_button.clicked.connect(self.clear_preview)
        preview_controls_row.addWidget(clear_button)
        preview_header_layout.addLayout(preview_controls_row)
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
        self.reconciliation_dashboard = ReconciliationDashboard(self)
        self.preview_stack = QStackedWidget()
        self.preview_stack.setObjectName("previewStack")
        self.preview_stack.addWidget(self.preview_table)
        self.preview_stack.addWidget(self.reconciliation_dashboard)
        preview_layout.addWidget(self.preview_stack, stretch=1)
        self.workspace_splitter.addWidget(preview_card)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)
        self.workspace_splitter.setSizes([260, 420])
        root.addWidget(self.workspace_splitter, stretch=1)

        self.version_label = QLabel(f"Version {__version__} develop")
        self.version_label.setObjectName("versionLabel")
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        root.addWidget(self.version_label)

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
        self._remove_result_views()
        panel = self._panels[source]
        panel.clear_mappings()
        panel.set_dataset(dataset.path, dataset.columns)
        self._auto_select_mappings(source, dataset.columns)
        self._add_preview_source(source)
        self._select_preview_source(source)
        return True

    def _auto_select_mappings(
        self,
        source: DataSource,
        columns: tuple[str, ...],
    ) -> None:
        panel = self._panels[source]
        fields = [field for field in MAPPING_FIELDS if field.source == source]
        for field in fields:
            suggestion = self._mapping_preferences.suggest(field, columns)
            if suggestion:
                panel.select_column(field.key, suggestion)

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
        if source_value in {source.value for source in DataSource}:
            self._show_preview(DataSource(source_value))
        elif source_value:
            self._show_result(source_value)

    def _show_preview(self, source: DataSource) -> None:
        dataset = self._state.dataset_for(source)
        if dataset is None:
            return

        self.preview_stack.setCurrentWidget(self.preview_table)
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

    def run_reconciliation(self) -> bool:
        """Segment both datasets, search inventory, and show the match table."""
        validation = self._validator.validate(self._state)
        if not validation.is_valid:
            QMessageBox.warning(
                self,
                "Configuracion incompleta",
                "\n".join(validation.errors),
            )
            self.status_label.setText("Configuracion incompleta")
            return False

        try:
            report = self._reconciler.reconcile(self._state)
        except ReconciliationError as exc:
            QMessageBox.warning(self, "No fue posible procesar", str(exc))
            self.status_label.setText("No fue posible procesar los archivos")
            return False

        self._state.set_reconciliation_report(report)
        self.reconciliation_dashboard.set_report(report)
        self.export_report_button.setEnabled(True)
        self._add_result_views()
        self._select_result_view(self.BI_DASHBOARD)
        QMessageBox.information(
            self,
            "Cruce completado",
            report.build_summary(),
        )
        return True

    def run_quick_search(self) -> bool:
        """Interpret a material query and display compatible inventory rows."""
        query_text = self.search_input.text().strip()
        try:
            results = self._reconciler.search_inventory(
                self._state,
                query_text,
            )
        except ReconciliationError as exc:
            QMessageBox.warning(self, "No fue posible buscar", str(exc))
            self.status_label.setText("No fue posible buscar en inventario")
            return False

        self._search_results = results
        if self.preview_source_combo.findData(self.QUICK_SEARCH_RESULTS) < 0:
            self.preview_source_combo.addItem(
                "Busqueda rapida",
                self.QUICK_SEARCH_RESULTS,
            )
        self.preview_source_combo.setEnabled(True)
        self._select_result_view(self.QUICK_SEARCH_RESULTS)
        if results.empty:
            QMessageBox.information(
                self,
                "Sin coincidencias",
                "No se encontraron materiales compatibles con la busqueda.",
            )
        return True

    def export_reconciliation_report(self) -> bool:
        """Save the latest segmentation and reconciliation report to Excel."""
        if self._state.reconciliation_report is None:
            QMessageBox.warning(
                self,
                "Sin reporte",
                "Ejecuta la segmentacion antes de exportar el reporte.",
            )
            return False

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar reporte de segmentacion",
            "reporte_segmentacion_hermes.xlsx",
            "Archivos Excel (*.xlsx)",
        )
        if not path:
            return False

        output_path = Path(path)
        if output_path.suffix.lower() != ".xlsx":
            output_path = output_path.with_suffix(".xlsx")

        try:
            self._write_reconciliation_report(output_path)
        except OSError as exc:
            QMessageBox.warning(
                self,
                "No fue posible exportar",
                f"No se pudo guardar el reporte:\n{exc}",
            )
            return False

        QMessageBox.information(
            self,
            "Reporte exportado",
            f"El reporte de segmentacion se guardo en:\n{output_path}",
        )
        self.status_label.setText(f"Reporte de segmentacion exportado: {output_path}")
        return True

    def _write_reconciliation_report(self, path: Path) -> None:
        report = self._state.reconciliation_report
        if report is None:
            return

        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            report.user_report.to_excel(
                writer,
                sheet_name="Requerimientos",
                index=False,
            )
            for worksheet in writer.sheets.values():
                for column_cells in worksheet.columns:
                    header = column_cells[0]
                    if header.value is None:
                        continue
                    width = min(max(len(str(header.value)) + 4, 14), 48)
                    worksheet.column_dimensions[header.column_letter].width = width

    def _set_mapping(self, field_key: str, column: str) -> None:
        self._state.set_mapping(field_key, column)
        self._mapping_preferences.remember(field_key, column)
        self._remove_result_views()

    def _add_result_views(self) -> None:
        result_views = (
            ("Resumen BI", self.BI_DASHBOARD),
            ("Reporte final", self.USER_REPORT),
            ("Cruce de inventario", self.MATCH_RESULTS),
            ("Segmentacion de requerimientos", self.REQUIREMENT_SEGMENTATION),
            ("Segmentacion de inventario", self.INVENTORY_SEGMENTATION),
        )
        for label, key in result_views:
            if self.preview_source_combo.findData(key) < 0:
                self.preview_source_combo.addItem(label, key)
        self.preview_source_combo.setEnabled(True)

    def _remove_result_views(self) -> None:
        self._search_results = None
        self.reconciliation_dashboard.clear()
        self.export_report_button.setEnabled(False)
        for index in range(self.preview_source_combo.count() - 1, -1, -1):
            value = self.preview_source_combo.itemData(index)
            if isinstance(value, str) and value.startswith("result:"):
                self.preview_source_combo.removeItem(index)

    def _select_result_view(self, key: str) -> None:
        index = self.preview_source_combo.findData(key)
        self.preview_source_combo.blockSignals(True)
        self.preview_source_combo.setCurrentIndex(index)
        self.preview_source_combo.blockSignals(False)
        self._show_result(key)

    def _show_result(self, key: str) -> None:
        if key == self.QUICK_SEARCH_RESULTS:
            if self._search_results is None:
                return
            self.preview_stack.setCurrentWidget(self.preview_table)
            self.preview_model.set_dataframe(
                self._search_results,
                limit_rows=False,
            )
            self.preview_table.resizeColumnsToContents()
            self.status_label.setText(
                "Busqueda rapida: "
                f"{len(self._search_results)} coincidencias encontradas"
            )
            return

        report = self._state.reconciliation_report
        if report is None:
            return
        if key == self.BI_DASHBOARD:
            self.reconciliation_dashboard.set_report(report)
            self.preview_stack.setCurrentWidget(self.reconciliation_dashboard)
            self.status_label.setText("Resumen BI: " + report.build_summary())
            return

        views = {
            self.USER_REPORT: (
                report.user_report,
                f"Reporte final: {len(report.user_report)} filas",
            ),
            self.MATCH_RESULTS: (
                report.matches,
                f"Cruce de inventario: {report.build_summary()}",
            ),
            self.REQUIREMENT_SEGMENTATION: (
                report.requirements,
                f"Requerimientos segmentados: {len(report.requirements)} filas",
            ),
            self.INVENTORY_SEGMENTATION: (
                report.inventory,
                f"Inventario segmentado: {len(report.inventory)} filas",
            ),
        }
        dataframe, status = views[key]
        self.preview_stack.setCurrentWidget(self.preview_table)
        self.preview_model.set_dataframe(dataframe, limit_rows=False)
        self.preview_table.resizeColumnsToContents()
        self.status_label.setText(status)

    def clear_preview(self) -> None:
        """Clear only the table view while preserving loaded datasets."""
        self.preview_model.clear()
        self.reconciliation_dashboard.clear()
        self.status_label.setText("Vista previa limpia")

    def _toggle_configuration_panel(self) -> None:
        if not self.configuration_panel.isHidden():
            sizes = self.workspace_splitter.sizes()
            if all(size > 0 for size in sizes):
                self._configuration_splitter_sizes = sizes
            self.configuration_panel.setVisible(False)
            self.configuration_toggle_button.setText("Mostrar config.")
            self.workspace_splitter.setSizes([0, 1])
            return

        self.configuration_panel.setVisible(True)
        self.configuration_toggle_button.setText("Ocultar config.")
        self.workspace_splitter.setSizes(self._configuration_splitter_sizes)

    def _set_dark_mode(self, enabled: bool) -> None:
        self._dark_mode = enabled
        self._apply_styles()
        self.reconciliation_dashboard.set_dark_mode(enabled)

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
            QFrame#quickSearchCard {
                background-color: #ffffff;
                border: 1px solid #e3e7ed;
                border-radius: 10px;
            }
            QFrame#configurationPanel {
                background-color: transparent;
                border: 0;
            }
            QSplitter#workspaceSplitter::handle:vertical {
                background-color: #dce1e8;
                height: 6px;
                margin: 1px 0;
            }
            QSplitter#workspaceSplitter::handle:vertical:hover {
                background-color: #c4ccd8;
            }
            QLabel#quickSearchLabel {
                color: #526176;
                font-weight: 700;
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
                margin-top: 18px;
                padding: 20px 14px 14px 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 14px;
                top: -2px;
                padding: 0 6px;
            }
            QLabel#filePath {
                color: #748196;
                font-size: 12px;
                padding: 2px 1px 8px 1px;
            }
            QScrollArea#mappingScrollArea,
            QWidget#mappingFormContainer {
                background-color: transparent;
                border: 0;
            }
            QLabel#mappingFieldLabel {
                color: #526176;
                font-size: 11px;
                font-weight: 700;
            }
            QFrame#mappingFieldRow {
                background-color: transparent;
                border: 0;
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
            QPushButton:disabled {
                background-color: #f1f3f5;
                border-color: #dce1e8;
                color: #9aa4b2;
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
            QComboBox#mappingCombo {
                min-height: 18px;
                padding: 4px 9px;
            }
            QLineEdit#quickSearchInput {
                background-color: #fbfcfd;
                border: 1px solid #dce1e8;
                border-radius: 7px;
                color: #263247;
                min-height: 20px;
                padding: 6px 10px;
            }
            QLineEdit#quickSearchInput:focus {
                background-color: #ffffff;
                border-color: #6377d8;
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
            QLabel#versionLabel {
                color: #8b97a8;
                font-size: 11px;
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
            QFrame#quickSearchCard,
            QScrollArea#mappingScrollArea,
            QWidget#mappingFormContainer,
            QFrame#configurationPanel,
            QGroupBox,
            QFrame#previewCard {
                background-color: #182235;
                border-color: #334155;
            }
            QFrame#configurationPanel {
                background-color: transparent;
                border: 0;
            }
            QSplitter#workspaceSplitter::handle:vertical {
                background-color: #334155;
            }
            QSplitter#workspaceSplitter::handle:vertical:hover {
                background-color: #53627a;
            }
            QLabel#eyebrow,
            QLabel#subtitle,
            QLabel#filePath,
            QLabel#mappingFieldLabel,
            QLabel#status,
            QLabel#previewSourceLabel,
            QLabel#quickSearchLabel,
            QLabel#versionLabel {
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
            QPushButton:disabled {
                background-color: #172133;
                border-color: #334155;
                color: #6f7d92;
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
            QComboBox#previewSource,
            QLineEdit#quickSearchInput {
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
            QLineEdit#quickSearchInput:focus {
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
