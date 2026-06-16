"""Export Hermes material parser results for manual validation.

Usage:
    .venv/bin/python scripts/export_material_categorization.py INPUT.xlsx \
        --output validacion_categorizacion_materiales.xlsx
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hermes.domain.materials import MaterialFamily, ParsedMaterial  # noqa: E402
from hermes.services.material_parser import MaterialParser  # noqa: E402


DEFAULT_MATERIAL_COLUMN = "Data_DescripcionMaterial"
DEFAULT_ITEM_COLUMN = "Data_DescripcionPartida"


def _sheet_value(value: str | None) -> str | int:
    if value is None:
        return 0
    try:
        return int(value)
    except ValueError:
        return value


def _cell_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return "; ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _warnings_text(parsed: ParsedMaterial) -> str:
    return "; ".join(parsed.warnings)


def _evidence_text(parsed: ParsedMaterial) -> str:
    payload = [item.to_dict() for item in parsed.evidence_spans]
    return json.dumps(payload, ensure_ascii=False)


def _result_row(parsed: ParsedMaterial) -> dict[str, Any]:
    requires_review = "review_required" in parsed.warnings
    return {
        "parser_source_row": parsed.source_row,
        "parser_family": parsed.family.value,
        "parser_is_programmed_family": parsed.family is not MaterialFamily.UNKNOWN,
        "parser_confidence_score": parsed.confidence_score,
        "parser_requires_review": requires_review,
        "parser_warnings": _warnings_text(parsed),
        "parser_canonical_key": parsed.canonical_key,
        "parser_normalized_description": parsed.normalized_description,
        "parser_evidence_spans": _evidence_text(parsed),
        "manual_family_ok": "",
        "manual_expected_family": "",
        "manual_notes": "",
    }


def export_validation_file(
    input_path: Path,
    output_path: Path,
    sheet: str | int,
    material_column: str,
    item_column: str,
    first_source_row: int,
    programmed_only: bool,
    use_item_fallback: bool,
) -> None:
    dataframe = pd.read_excel(input_path, sheet_name=sheet, engine="openpyxl")
    if material_column not in dataframe.columns:
        raise ValueError(f"Missing material column: {material_column}")

    parser = MaterialParser()
    parsed_rows: list[ParsedMaterial] = []
    for offset, (_, row) in enumerate(dataframe.iterrows()):
        source_row = first_source_row + offset
        material_description = row[material_column]
        if use_item_fallback:
            item_description = (
                row[item_column] if item_column in dataframe.columns else None
            )
            parsed = parser.parse_row(
                source_row=source_row,
                material_description=material_description,
                item_description=item_description,
            )
        else:
            parsed = parser.parse_description(material_description, source_row)
        parsed_rows.append(parsed)

    result_rows = [_result_row(parsed) for parsed in parsed_rows]
    attribute_names = sorted(
        {
            attribute
            for parsed in parsed_rows
            for attribute in parsed.attributes.keys()
        }
    )
    for result, parsed in zip(result_rows, parsed_rows, strict=True):
        for attribute in attribute_names:
            result[f"attr_{attribute}"] = _cell_value(
                parsed.attributes.get(attribute, "")
            )

    parsed_frame = pd.DataFrame(result_rows)
    detail = pd.concat([dataframe.reset_index(drop=True), parsed_frame], axis=1)
    if programmed_only:
        detail = detail[detail["parser_is_programmed_family"]].copy()

    summary = pd.DataFrame(
        Counter(parsed.family.value for parsed in parsed_rows).most_common(),
        columns=["parser_family", "row_count"],
    )
    warning_summary = pd.DataFrame(
        Counter(
            warning for parsed in parsed_rows for warning in parsed.warnings
        ).most_common(),
        columns=["parser_warning", "row_count"],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".csv":
        detail.to_csv(output_path, index=False)
        return

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        detail.to_excel(writer, index=False, sheet_name="detalle")
        summary.to_excel(writer, index=False, sheet_name="resumen_familias")
        warning_summary.to_excel(
            writer,
            index=False,
            sheet_name="resumen_warnings",
        )
        worksheet = writer.sheets["detalle"]
        worksheet.freeze_panes = "A2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export parser output columns for manual validation.",
    )
    parser.add_argument("input", type=Path, help="Input .xlsx catalog path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("validacion_categorizacion_materiales.xlsx"),
        help="Output .xlsx or .csv path.",
    )
    parser.add_argument(
        "--sheet",
        default=None,
        help="Sheet name or zero-based sheet index. Defaults to first sheet.",
    )
    parser.add_argument(
        "--material-column",
        default=DEFAULT_MATERIAL_COLUMN,
        help="Column containing the material description.",
    )
    parser.add_argument(
        "--item-column",
        default=DEFAULT_ITEM_COLUMN,
        help="Optional item description column used only with --use-item-fallback.",
    )
    parser.add_argument(
        "--first-source-row",
        type=int,
        default=2,
        help="Excel row number for the first data row.",
    )
    parser.add_argument(
        "--programmed-only",
        action="store_true",
        help="Export only rows classified as a programmed family.",
    )
    parser.add_argument(
        "--use-item-fallback",
        action="store_true",
        help="Use Data_DescripcionPartida as fallback when material text is empty.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    export_validation_file(
        input_path=args.input,
        output_path=args.output,
        sheet=_sheet_value(args.sheet),
        material_column=args.material_column,
        item_column=args.item_column,
        first_source_row=args.first_source_row,
        programmed_only=args.programmed_only,
        use_item_fallback=args.use_item_fallback,
    )
    print(f"Exported validation file: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
