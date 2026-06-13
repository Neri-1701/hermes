from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import pandas as pd


class DataSource(str, Enum):
    INVENTORY = "inventory"
    REQUIREMENTS = "requirements"

    @property
    def display_name(self) -> str:
        names = {
            DataSource.INVENTORY: "inventario",
            DataSource.REQUIREMENTS: "requerimientos",
        }
        return names[self]


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    source: DataSource
    path: Path
    dataframe: pd.DataFrame

    @property
    def columns(self) -> tuple[str, ...]:
        return tuple(str(column) for column in self.dataframe.columns)


@dataclass
class HermesState:
    datasets: dict[DataSource, LoadedDataset] = field(default_factory=dict)
    mappings: dict[str, str] = field(default_factory=dict)

    def set_dataset(self, dataset: LoadedDataset) -> None:
        self.datasets[dataset.source] = dataset

    def dataset_for(self, source: DataSource) -> LoadedDataset | None:
        return self.datasets.get(source)

    def set_mapping(self, field_key: str, column: str) -> None:
        if column:
            self.mappings[field_key] = column
        else:
            self.mappings.pop(field_key, None)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    errors: tuple[str, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.errors
