"""Controlled text normalization that preserves links to the raw text."""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

from hermes.domain.materials import EvidenceSpan


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """Normalized text plus a character-level map back to its source."""

    raw: str
    text: str
    raw_starts: tuple[int, ...]
    raw_ends: tuple[int, ...]

    def evidence(self, field: str, start: int, end: int) -> EvidenceSpan:
        """Translate a normalized span into an exact raw-text span."""
        if start < 0 or end <= start or end > len(self.text):
            raise ValueError("Invalid normalized evidence span.")
        raw_start = self.raw_starts[start]
        raw_end = self.raw_ends[end - 1]
        return EvidenceSpan(
            field=field,
            text=self.raw[raw_start:raw_end],
            start=raw_start,
            end=raw_end,
        )


def _without_accents(character: str) -> str:
    decomposed = unicodedata.normalize("NFD", character)
    return "".join(
        item for item in decomposed if unicodedata.category(item) != "Mn"
    ).upper()


def normalize_text(text: object) -> NormalizedText:
    """Uppercase and standardize text without losing raw evidence offsets."""
    raw = "" if text is None else str(text)
    expanded: list[tuple[str, int, int]] = []
    index = 0

    while index < len(raw):
        if raw.startswith("_x000D_", index):
            expanded.append((" ", index, index + len("_x000D_")))
            index += len("_x000D_")
            continue

        character = raw[index]
        if character in "\n\r\t":
            replacement = " "
        elif character in {"Ø", "ø"}:
            replacement = " DIAMETRO "
        elif character in {"°", "º"}:
            replacement = " GRADOS "
        elif character in {"“", "”", "″"}:
            replacement = '"'
        elif character in {"–", "—"}:
            replacement = "-"
        else:
            replacement = _without_accents(character)

        for normalized_character in replacement:
            expanded.append((normalized_character, index, index + 1))
        index += 1

    collapsed: list[tuple[str, int, int]] = []
    for character, raw_start, raw_end in expanded:
        if character.isspace():
            if not collapsed or collapsed[-1][0] == " ":
                continue
            collapsed.append((" ", raw_start, raw_end))
            continue
        collapsed.append((character, raw_start, raw_end))

    if collapsed and collapsed[-1][0] == " ":
        collapsed.pop()

    return NormalizedText(
        raw=raw,
        text="".join(character for character, _, _ in collapsed),
        raw_starts=tuple(raw_start for _, raw_start, _ in collapsed),
        raw_ends=tuple(raw_end for _, _, raw_end in collapsed),
    )
