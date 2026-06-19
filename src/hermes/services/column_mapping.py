"""Suggest and remember spreadsheet column mappings."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from pathlib import Path

from hermes.config import MappingField


class ColumnMappingPreferences:
    """Persist lightweight user column preferences between application runs."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or self._default_path()
        self._latest = self._load()

    def suggest(
        self,
        field: MappingField,
        columns: tuple[str, ...],
    ) -> str:
        """Return the most likely column for `field`, or an empty string."""
        if not columns:
            return ""

        remembered = self._latest.get(field.key)
        if remembered in columns:
            return remembered

        scored = [
            (self._score(field, column), -index, column)
            for index, column in enumerate(columns)
        ]
        score, _position, column = max(scored)
        return column if score >= 8 else ""

    def remember(self, field_key: str, column: str) -> None:
        """Store the latest explicit mapping selected by the user."""
        if not column:
            return
        if self._latest.get(field_key) == column:
            return
        self._latest[field_key] = column
        self._save()

    @staticmethod
    def _default_path() -> Path:
        override = os.environ.get("HERMES_COLUMN_MAPPING_PREFERENCES")
        if override:
            return Path(override)
        return Path.home() / ".hermes" / "column_mappings.json"

    def _load(self) -> dict[str, str]:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(payload, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(self._latest, indent=2, sort_keys=True),
                encoding="utf-8",
            )
        except OSError:
            # Preferences should improve the workflow, never block it.
            return

    @classmethod
    def _score(cls, field: MappingField, column: str) -> int:
        normalized = cls._normalize(column)
        tokens = set(normalized.split())
        score = 0
        for keyword in field.keywords:
            normalized_keyword = cls._normalize(keyword)
            weight = 4 if normalized_keyword in {"material", "item"} else 12
            if normalized_keyword in tokens:
                score += weight
            elif normalized_keyword and normalized_keyword in normalized:
                score += max(weight - 4, 2)
        if "descripcion" in normalized and "description" in field.keywords:
            score += 4
        if "cantidad" in normalized and "quantity" in field.keywords:
            score += 4
        return score

    @staticmethod
    def _normalize(value: str) -> str:
        decomposed = unicodedata.normalize("NFKD", value)
        ascii_text = "".join(
            char for char in decomposed if not unicodedata.combining(char)
        )
        return re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).strip()
