"""Domain models for loaded spreadsheets and setup state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pandas as pd

from hermes.domain.reconciliation import ReconciliationReport


class DataSource(str, Enum):
    """Business categories of spreadsheet input accepted by Hermes."""

    INVENTORY = "inventory"
    REQUIREMENTS = "requirements"

    @property
    def display_name(self) -> str:
        """Return the Spanish name used in the interface and messages."""
        names = {
            DataSource.INVENTORY: "inventario",
            DataSource.REQUIREMENTS: "requerimientos",
        }
        return names[self]


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    """Loaded spreadsheet associated with its source and resolved file path."""

    source: DataSource
    path: Path
    dataframe: pd.DataFrame

    @property
    def columns(self) -> tuple[str, ...]:
        """Return immutable text labels suitable for column mapping controls."""
        return tuple(str(column) for column in self.dataframe.columns)


@dataclass
class HermesState:
    """Mutable collection of loaded datasets and user-selected mappings."""

    datasets: dict[DataSource, LoadedDataset] = field(default_factory=dict)
    mappings: dict[str, str] = field(default_factory=dict)
    reconciliation_report: ReconciliationReport | None = None

    def set_dataset(self, dataset: LoadedDataset) -> None:
        """Store or replace the dataset for its declared source."""
        self.datasets[dataset.source] = dataset
        self.reconciliation_report = None

    def dataset_for(self, source: DataSource) -> LoadedDataset | None:
        """Return the dataset loaded for a source, if one is available."""
        return self.datasets.get(source)

    def set_mapping(self, field_key: str, column: str) -> None:
        """Store a field mapping, removing it when the column is empty."""
        previous = self.mappings.get(field_key)
        if column:
            self.mappings[field_key] = column
        else:
            self.mappings.pop(field_key, None)
        if previous != (column or None):
            self.reconciliation_report = None

    def set_reconciliation_report(self, report: ReconciliationReport) -> None:
        """Store the latest complete processing result."""
        self.reconciliation_report = report


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """Validation outcome containing all user-facing setup errors."""

    errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        """Return whether validation completed without errors."""
        return not self.errors
