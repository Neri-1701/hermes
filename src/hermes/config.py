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
    keywords: tuple[str, ...] = ()


MAPPING_FIELDS = (
    MappingField(
        key="inventory_description",
        label="Columna de descripcion",
        source=DataSource.INVENTORY,
        keywords=(
            "descripcion",
            "description",
            "material",
            "larga",
            "long",
            "detalle",
        ),
    ),
    MappingField(
        key="inventory_code",
        label="Columna de codigo de material",
        source=DataSource.INVENTORY,
        keywords=(
            "codigo",
            "code",
            "material",
            "item",
            "clave",
            "sku",
        ),
    ),
    MappingField(
        key="inventory_quantity",
        label="Columna de cantidad disponible",
        source=DataSource.INVENTORY,
        keywords=(
            "cantidad",
            "quantity",
            "disponible",
            "available",
            "existencia",
            "stock",
            "saldo",
        ),
    ),
    MappingField(
        key="requirements_description",
        label="Columna de descripcion solicitada",
        source=DataSource.REQUIREMENTS,
        keywords=(
            "descripcion",
            "description",
            "material",
            "solicitada",
            "requerida",
            "larga",
            "long",
        ),
    ),
    MappingField(
        key="requirements_quantity",
        label="Columna de cantidad requerida",
        source=DataSource.REQUIREMENTS,
        keywords=(
            "cantidad",
            "quantity",
            "requerida",
            "required",
            "solicitada",
            "qty",
        ),
    ),
)
