"""Static application settings and required spreadsheet mappings."""

from __future__ import annotations

from dataclasses import dataclass

from hermes.domain.models import DataSource

APP_TITLE = "Hermes"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 720
MIN_WINDOW_WIDTH = 1000
MIN_WINDOW_HEIGHT = 620
PREVIEW_LIMIT = 100


@dataclass(frozen=True, slots=True)
class MappingField:
    """Required business field that a user maps to a spreadsheet column."""

    key: str
    label: str
    source: DataSource
    required: bool = True


MAPPING_FIELDS = (
    MappingField(
        key="inventory_description",
        label="Columna de descripcion",
        source=DataSource.INVENTORY,
    ),
    MappingField(
        key="inventory_code",
        label="Columna de codigo de material",
        source=DataSource.INVENTORY,
    ),
    MappingField(
        key="inventory_quantity",
        label="Columna de cantidad disponible",
        source=DataSource.INVENTORY,
    ),
    MappingField(
        key="requirements_udc",
        label="Columna UDC",
        source=DataSource.REQUIREMENTS,
    ),
    MappingField(
        key="requirements_date",
        label="Columna de fecha de programa",
        source=DataSource.REQUIREMENTS,
    ),
    MappingField(
        key="requirements_description",
        label="Columna de descripcion solicitada",
        source=DataSource.REQUIREMENTS,
    ),
    MappingField(
        key="requirements_item_description",
        label="Descripcion de partida de respaldo (opcional)",
        source=DataSource.REQUIREMENTS,
        required=False,
    ),
    MappingField(
        key="requirements_quantity",
        label="Columna de cantidad requerida",
        source=DataSource.REQUIREMENTS,
    ),
)
