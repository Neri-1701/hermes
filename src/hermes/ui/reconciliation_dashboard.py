"""Visual dashboard widgets for reconciliation BI results."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from hermes.config import PREVIEW_LIMIT
from hermes.domain.reconciliation import ReconciliationReport
from hermes.services.bi_summary import (
    MetricCard,
    ReconciliationDashboardSummary,
    build_reconciliation_dashboard_summary,
)
from hermes.ui.dataframe_model import DataFrameTableModel


class ReconciliationDashboard(QWidget):
    """Dashboard panel that renders relevant BI after a reconciliation run."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("reconciliationDashboard")
        self._card_widgets: list[_MetricCardWidget] = []
        self._status_rows: list[_DistributionRow] = []
        self._family_model = DataFrameTableModel(PREVIEW_LIMIT, self)
        self._critical_model = DataFrameTableModel(PREVIEW_LIMIT, self)
        self._inventory_model = DataFrameTableModel(PREVIEW_LIMIT, self)
        self._build_ui()
        self.clear()

    def set_report(self, report: ReconciliationReport) -> None:
        """Build and display dashboard data for the provided report."""
        self.set_summary(build_reconciliation_dashboard_summary(report))

    def set_summary(self, summary: ReconciliationDashboardSummary) -> None:
        """Display an already computed dashboard summary."""
        self.empty_label.setVisible(False)
        self.dashboard_body.setVisible(True)
        self.coverage_bar.setValue(round(summary.coverage_pct))
        self.coverage_label.setText(f"{summary.coverage_pct:.1f}% de cobertura total")

        for widget, card in zip(self._card_widgets, summary.cards):
            widget.set_metric(card)

        for row in self._status_rows:
            row.setVisible(False)
        for index, item in enumerate(summary.status_distribution):
            if index >= len(self._status_rows):
                row = _DistributionRow()
                self.status_layout.addWidget(row)
                self._status_rows.append(row)
            self._status_rows[index].set_distribution(
                item.label,
                item.count,
                item.percentage,
                item.level,
            )
            self._status_rows[index].setVisible(True)

        self._family_model.set_dataframe(summary.family_summary, limit_rows=False)
        self.family_table.resizeColumnsToContents()
        self._critical_model.set_dataframe(
            summary.critical_requirements,
            limit_rows=False,
        )
        self.critical_table.resizeColumnsToContents()
        self._inventory_model.set_dataframe(summary.inventory_usage, limit_rows=False)
        self.inventory_table.resizeColumnsToContents()

    def clear(self) -> None:
        """Reset the dashboard to its initial empty state."""
        self.empty_label.setVisible(True)
        self.dashboard_body.setVisible(False)
        self.coverage_bar.setValue(0)
        self.coverage_label.setText("Sin cruce ejecutado")
        for widget in self._card_widgets:
            widget.set_metric(MetricCard("-", "-", ""))
        for row in self._status_rows:
            row.setVisible(False)
        self._family_model.clear()
        self._critical_model.clear()
        self._inventory_model.clear()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        scroll = QScrollArea()
        scroll.setObjectName("dashboardScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(scroll)

        container = QWidget()
        container.setObjectName("dashboardContainer")
        scroll.setWidget(container)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(14)

        self.empty_label = QLabel(
            "Ejecuta la segmentacion para generar el resumen visual del cruce."
        )
        self.empty_label.setObjectName("dashboardEmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self.dashboard_body = QWidget()
        self.dashboard_body.setObjectName("dashboardBody")
        body_layout = QVBoxLayout(self.dashboard_body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(14)
        layout.addWidget(self.dashboard_body)

        self.coverage_label = QLabel("Sin cruce ejecutado")
        self.coverage_label.setObjectName("dashboardCoverageLabel")
        body_layout.addWidget(self.coverage_label)

        self.coverage_bar = QProgressBar()
        self.coverage_bar.setObjectName("dashboardCoverageBar")
        self.coverage_bar.setRange(0, 100)
        self.coverage_bar.setTextVisible(False)
        body_layout.addWidget(self.coverage_bar)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        for _ in range(4):
            card = _MetricCardWidget()
            self._card_widgets.append(card)
            cards_row.addWidget(card, stretch=1)
        body_layout.addLayout(cards_row)

        status_card = _SectionCard("Estado del cruce")
        self.status_layout = QVBoxLayout()
        self.status_layout.setSpacing(8)
        status_card.content_layout.addLayout(self.status_layout)
        body_layout.addWidget(status_card)

        family_card = _SectionCard("Resumen por familia")
        self.family_table = self._build_table(self._family_model)
        family_card.content_layout.addWidget(self.family_table)
        body_layout.addWidget(family_card)

        critical_card = _SectionCard("Partidas criticas")
        self.critical_table = self._build_table(self._critical_model)
        critical_card.content_layout.addWidget(self.critical_table)
        body_layout.addWidget(critical_card)

        inventory_card = _SectionCard("Uso de inventario")
        self.inventory_table = self._build_table(self._inventory_model)
        inventory_card.content_layout.addWidget(self.inventory_table)
        body_layout.addWidget(inventory_card)

        self.setStyleSheet(
            """
            QWidget#reconciliationDashboard,
            QWidget#dashboardContainer,
            QWidget#dashboardBody {
                background-color: transparent;
            }
            QLabel#dashboardEmptyState {
                color: #748196;
                font-size: 14px;
                padding: 28px;
            }
            QLabel#dashboardCoverageLabel {
                color: #263247;
                font-size: 15px;
                font-weight: 700;
            }
            QFrame#dashboardMetricCard,
            QFrame#dashboardSectionCard {
                background-color: #ffffff;
                border: 1px solid #e3e7ed;
                border-radius: 12px;
            }
            QLabel#metricTitle,
            QLabel#sectionCardTitle,
            QLabel#distributionLabel {
                color: #526176;
                font-weight: 700;
            }
            QLabel#metricValue {
                color: #172033;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#metricDetail,
            QLabel#distributionDetail {
                color: #748196;
                font-size: 12px;
            }
            QProgressBar#dashboardCoverageBar {
                background-color: #eef1f5;
                border: 0;
                border-radius: 6px;
                min-height: 12px;
                max-height: 12px;
            }
            QProgressBar#dashboardCoverageBar::chunk {
                background-color: #4056c7;
                border-radius: 6px;
            }
            """
        )

    @staticmethod
    def _build_table(model: DataFrameTableModel) -> QTableView:
        table = QTableView()
        table.setModel(model)
        table.setAlternatingRowColors(True)
        table.setSortingEnabled(False)
        table.setShowGrid(False)
        table.setCornerButtonEnabled(False)
        table.horizontalHeader().setDefaultSectionSize(150)
        table.verticalHeader().setDefaultSectionSize(32)
        table.setMinimumHeight(180)
        return table


class _MetricCardWidget(QFrame):
    """Small card used by the dashboard metric strip."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardMetricCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(4)

        self.title_label = QLabel()
        self.title_label.setObjectName("metricTitle")
        layout.addWidget(self.title_label)

        self.value_label = QLabel()
        self.value_label.setObjectName("metricValue")
        layout.addWidget(self.value_label)

        self.detail_label = QLabel()
        self.detail_label.setObjectName("metricDetail")
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

    def set_metric(self, metric: MetricCard) -> None:
        self.title_label.setText(metric.title)
        self.value_label.setText(metric.value)
        self.detail_label.setText(metric.detail)
        self.setProperty("level", metric.level)
        self.style().unpolish(self)
        self.style().polish(self)


class _DistributionRow(QWidget):
    """Horizontal distribution row with a label, percentage and bar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.label = QLabel()
        self.label.setObjectName("distributionLabel")
        self.label.setMinimumWidth(150)
        layout.addWidget(self.label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        layout.addWidget(self.bar, stretch=1)

        self.detail = QLabel()
        self.detail.setObjectName("distributionDetail")
        self.detail.setMinimumWidth(90)
        self.detail.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.detail)

    def set_distribution(
        self,
        label: str,
        count: int,
        percentage: float,
        level: str,
    ) -> None:
        self.label.setText(label)
        self.bar.setValue(round(percentage))
        self.detail.setText(f"{count} | {percentage:.1f}%")
        self.setProperty("level", level)
        self.style().unpolish(self)
        self.style().polish(self)


class _SectionCard(QFrame):
    """Reusable dashboard section card."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardSectionCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(10)

        title_label = QLabel(title)
        title_label.setObjectName("sectionCardTitle")
        layout.addWidget(title_label)

        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        layout.addLayout(self.content_layout)
