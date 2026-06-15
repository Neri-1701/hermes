"""Validate whether the data-loading workflow is ready for processing."""

from __future__ import annotations

from collections.abc import Iterable

from hermes.config import MAPPING_FIELDS, MappingField
from hermes.domain.models import DataSource, HermesState, ValidationResult


class SetupValidator:
    """Check required datasets and field-to-column mappings."""

    def __init__(self, fields: Iterable[MappingField] = MAPPING_FIELDS) -> None:
        """Create a validator for the supplied required mapping fields."""
        self._fields = tuple(fields)

    def validate(self, state: HermesState) -> ValidationResult:
        """Return every setup error found instead of stopping at the first."""
        errors: list[str] = []

        for source in DataSource:
            if state.dataset_for(source) is None:
                errors.append(f"Carga el archivo de {source.display_name}.")

        for field in self._fields:
            selected_column = state.mappings.get(field.key)
            if not selected_column:
                errors.append(f"Selecciona: {field.label}.")
                continue

            dataset = state.dataset_for(field.source)
            if dataset is not None and selected_column not in dataset.columns:
                errors.append(
                    f"La columna '{selected_column}' ya no existe en el archivo de "
                    f"{field.source.display_name}."
                )

        return ValidationResult(errors=tuple(errors))

    def build_summary(self, state: HermesState) -> str:
        """Describe mappings from a state previously accepted by `validate`.

        Required mappings are indexed directly because a missing key after
        successful validation represents incorrect caller usage.
        """
        lines = [
            "La configuracion de Hermes es valida.",
            "",
            "Mapeo seleccionado:",
        ]
        for field in self._fields:
            lines.append(f"- {field.label}: {state.mappings[field.key]}")

        lines.extend(
            [
                "",
                "La informacion esta lista para el siguiente paso de procesamiento.",
            ]
        )
        return "\n".join(lines)
