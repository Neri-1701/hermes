"""Visual dashboard widgets for reconciliation BI results."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
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


_LIGHT_PALETTE = {
    "accent": "#4056c7",
    "accent_soft": "#6377d8",
    "text": "#172033",
    "heading": "#FFFFFF",
    "slate": "#526176",
    "muted": "#748196",
    "gray": "#8b97a8",
    "gray_soft": "#cbd2dc",
    "surface": "#ffffff",
    "surface_alt": "#f8f9fb",
    "border": "#e3e7ed",
    "header": "#f2f4f7",
    "track": "#eef1f5",
    "chart_track": "#e8ebef",
    "selection": "#e3e8ff",
    "selection_text": "#1f2d5c",
}

_DARK_PALETTE = {
    "accent": "#8ea0ff",
    "accent_soft": "#6f83e7",
    "text": "#f1f5f9",
    "heading": "#e5e7eb",
    "slate": "#b8c4d6",
    "muted": "#9aa8bd",
    "gray": "#71839f",
    "gray_soft": "#46556c",
    "surface": "#182235",
    "surface_alt": "#1d293c",
    "border": "#334155",
    "header": "#202c40",
    "track": "#26344a",
    "chart_track": "#2d3b52",
    "selection": "#35456a",
    "selection_text": "#ffffff",
}


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
        self._dark_mode = False
        self._summary: ReconciliationDashboardSummary | None = None
        self._build_ui()
        self._apply_styles()
        self._apply_chart_track_color()
        self.clear()

    def set_dark_mode(self, enabled: bool) -> None:
        """Refresh the dashboard palette when the application theme changes."""
        if self._dark_mode == enabled:
            return
        self._dark_mode = enabled
        self._apply_styles()
        self._apply_chart_track_color()
        if self._summary is not None:
            self._render_summary(self._summary)

    def set_report(self, report: ReconciliationReport) -> None:
        """Build and display dashboard data for the provided report."""
        self.set_summary(build_reconciliation_dashboard_summary(report))

    def set_summary(self, summary: ReconciliationDashboardSummary) -> None:
        """Display an already computed dashboard summary."""
        self._summary = summary
        self._render_summary(summary)

    def _render_summary(self, summary: ReconciliationDashboardSummary) -> None:
        palette = self._palette()
        self.empty_label.setVisible(False)
        self.dashboard_body.setVisible(True)
        self.coverage_bar.setValue(round(summary.coverage_pct))
        self.coverage_label.setText(
            f"{summary.coverage_pct:.1f}% de partidas cubiertas"
        )
        pending_count = max(summary.requirement_count - summary.covered_count, 0)
        self.coverage_donut.set_segments(
            [
                ("Cubiertas", summary.covered_count, palette["accent"]),
                ("Pendientes", pending_count, palette["chart_track"]),
            ],
            f"{summary.coverage_pct:.1f}%",
            f"{summary.covered_count} de {summary.requirement_count} partidas",
        )
        self.status_donut.set_segments(
            [
                (item.label, item.count, _color_for_level(item.level, palette))
                for item in summary.status_distribution
            ],
            str(summary.requirement_count),
            "partidas procesadas",
        )
        self.inventory_donut.set_segments(
            [
                ("Utilizado", summary.inventory_assigned, palette["accent_soft"]),
                ("Restante", summary.inventory_remaining, palette["chart_track"]),
            ],
            f"{summary.inventory_usage_pct:.1f}%",
            "inventario utilizado",
        )

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
        self._summary = None
        self.empty_label.setVisible(True)
        self.dashboard_body.setVisible(False)
        self.coverage_bar.setValue(0)
        self.coverage_label.setText("Sin cruce ejecutado")
        self.coverage_donut.clear()
        self.status_donut.clear()
        self.inventory_donut.clear()
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

        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        self.coverage_donut = _DonutChartWidget("Cobertura de partidas")
        self.status_donut = _DonutChartWidget("Estado del cruce")
        self.inventory_donut = _DonutChartWidget("Uso de inventario")
        charts_row.addWidget(self.coverage_donut, stretch=1)
        charts_row.addWidget(self.status_donut, stretch=1)
        charts_row.addWidget(self.inventory_donut, stretch=1)
        body_layout.addLayout(charts_row)

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

    def _apply_styles(self) -> None:
        palette = self._palette()
        self.setStyleSheet(
            """
            QWidget#reconciliationDashboard,
            QWidget#dashboardContainer,
            QWidget#dashboardBody {
                background-color: transparent;
            }
            QLabel#dashboardEmptyState {
                color: %(muted)s;
                font-size: 14px;
                padding: 28px;
            }
            QLabel#dashboardCoverageLabel {
                color: %(heading)s;
                font-size: 15px;
                font-weight: 700;
            }
            QFrame#dashboardMetricCard,
            QFrame#dashboardSectionCard,
            QFrame#dashboardDonutCard {
                background-color: %(surface)s;
                border: 1px solid %(border)s;
                border-radius: 12px;
            }
            QLabel#metricTitle,
            QLabel#sectionCardTitle,
            QLabel#donutTitle,
            QLabel#distributionLabel {
                color: %(slate)s;
                font-weight: 700;
            }
            QLabel#metricValue {
                color: %(text)s;
                font-size: 22px;
                font-weight: 800;
            }
            QLabel#donutValue {
                color: %(text)s;
                font-size: 20px;
                font-weight: 800;
            }
            QLabel#metricDetail,
            QLabel#donutDetail,
            QLabel#donutLegend,
            QLabel#distributionDetail {
                color: %(muted)s;
                font-size: 12px;
            }
            QProgressBar#dashboardCoverageBar {
                background-color: %(track)s;
                border: 0;
                border-radius: 6px;
                min-height: 12px;
                max-height: 12px;
            }
            QProgressBar#dashboardCoverageBar::chunk {
                background-color: %(accent)s;
                border-radius: 6px;
            }
            QProgressBar#dashboardDistributionBar {
                background-color: %(track)s;
                border: 0;
                border-radius: 5px;
                min-height: 10px;
                max-height: 10px;
            }
            QProgressBar#dashboardDistributionBar::chunk {
                background-color: %(muted)s;
                border-radius: 5px;
            }
            QProgressBar#dashboardDistributionBar[level="success"]::chunk {
                background-color: %(accent)s;
            }
            QProgressBar#dashboardDistributionBar[level="warning"]::chunk {
                background-color: %(gray)s;
            }
            QProgressBar#dashboardDistributionBar[level="danger"]::chunk {
                background-color: %(slate)s;
            }
            QProgressBar#dashboardDistributionBar[level="neutral"]::chunk {
                background-color: %(gray_soft)s;
            }
            QTableView#dashboardTable {
                background-color: %(surface)s;
                alternate-background-color: %(surface_alt)s;
                border: 0;
                color: %(heading)s;
                gridline-color: %(border)s;
                outline: 0;
                selection-background-color: %(selection)s;
                selection-color: %(selection_text)s;
            }
            QTableView#dashboardTable QHeaderView::section {
                background-color: %(header)s;
                border: 0;
                border-bottom: 1px solid %(border)s;
                border-right: 1px solid %(border)s;
                color: %(slate)s;
                font-weight: 700;
                padding: 8px 10px;
            }
            QTableView#dashboardTable QTableCornerButton::section {
                background-color: %(header)s;
                border: 0;
            }
            """
            % palette
        )
        self._refresh_dynamic_styles()

    def _apply_chart_track_color(self) -> None:
        track_color = self._palette()["chart_track"]
        self.coverage_donut.set_track_color(track_color)
        self.status_donut.set_track_color(track_color)
        self.inventory_donut.set_track_color(track_color)

    def _palette(self) -> dict[str, str]:
        return _DARK_PALETTE if self._dark_mode else _LIGHT_PALETTE

    def _refresh_dynamic_styles(self) -> None:
        widgets = [
            self.coverage_bar,
            *self._card_widgets,
            *self._status_rows,
        ]
        for widget in widgets:
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    @staticmethod
    def _build_table(model: DataFrameTableModel) -> QTableView:
        table = QTableView()
        table.setObjectName("dashboardTable")
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


class _DonutChartWidget(QFrame):
    """Small donut chart card rendered with Qt painting."""

    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardDonutCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title_label = QLabel(title)
        title_label.setObjectName("donutTitle")
        layout.addWidget(title_label)

        self.chart = _DonutCanvas()
        layout.addWidget(self.chart, alignment=Qt.AlignmentFlag.AlignCenter)

        self.value_label = QLabel("-")
        self.value_label.setObjectName("donutValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("donutDetail")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setWordWrap(True)
        layout.addWidget(self.detail_label)

        self.legend_label = QLabel("")
        self.legend_label.setObjectName("donutLegend")
        self.legend_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.legend_label.setWordWrap(True)
        layout.addWidget(self.legend_label)

    def set_segments(
        self,
        segments: list[tuple[str, float, str]],
        value: str,
        detail: str,
    ) -> None:
        visible_segments = [
            (label, float(amount), color)
            for label, amount, color in segments
            if float(amount) > 0
        ]
        self.chart.set_segments(visible_segments)
        self.value_label.setText(value)
        self.detail_label.setText(detail)
        self.legend_label.setText(
            " | ".join(
                f"{label}: {_format_chart_value(amount)}"
                for label, amount, _color in visible_segments[:4]
            )
        )

    def clear(self) -> None:
        self.chart.set_segments([])
        self.value_label.setText("-")
        self.detail_label.setText("Sin datos")
        self.legend_label.setText("")

    def set_track_color(self, color: str) -> None:
        self.chart.set_track_color(color)


class _DonutCanvas(QWidget):
    """Paint only the donut ring; labels live in the containing card."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._segments: list[tuple[str, float, str]] = []
        self._track_color = _LIGHT_PALETTE["chart_track"]
        self.setFixedSize(118, 118)

    def set_segments(self, segments: list[tuple[str, float, str]]) -> None:
        self._segments = segments
        self.update()

    def set_track_color(self, color: str) -> None:
        self._track_color = color
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen_width = 16
        rect = QRectF(
            pen_width,
            pen_width,
            self.width() - pen_width * 2,
            self.height() - pen_width * 2,
        )

        background_pen = QPen(QColor(self._track_color), pen_width)
        background_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(background_pen)
        painter.drawArc(rect, 0, 360 * 16)

        total = sum(amount for _label, amount, _color in self._segments)
        if total <= 0:
            painter.end()
            return

        start_angle = 90 * 16
        for _label, amount, color in self._segments:
            span_angle = round(-amount / total * 360 * 16)
            pen = QPen(QColor(color), pen_width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            painter.drawArc(rect, start_angle, span_angle)
            start_angle += span_angle
        painter.end()


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
        self.bar.setObjectName("dashboardDistributionBar")
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
        self.bar.setProperty("level", level)
        self.bar.style().unpolish(self.bar)
        self.bar.style().polish(self.bar)
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


def _color_for_level(level: str, palette: dict[str, str]) -> str:
    colors = {
        "success": palette["accent"],
        "warning": palette["gray"],
        "danger": palette["slate"],
        "neutral": palette["gray_soft"],
    }
    return colors.get(level, palette["muted"])


def _format_chart_value(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value):,}"
    return f"{value:,.1f}"
