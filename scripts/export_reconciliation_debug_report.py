"""Export detailed reconciliation tables for developer validation.

Usage:
    .venv/bin/python scripts/export_reconciliation_debug_report.py

    # Or override any input explicitly:
    .venv/bin/python scripts/export_reconciliation_debug_report.py \
        inventory.xlsx requirements.xlsx --output debug_reconciliacion.xlsx \
        --inventory-description description --inventory-code code \
        --inventory-quantity available --requirements-description description \
        --requirements-quantity required
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from hermes.domain.models import DataSource, HermesState, LoadedDataset  # noqa: E402
from hermes.services.reconciliation import ReconciliationService  # noqa: E402

DEFAULT_FIXTURES_DIR = ROOT / "data" / "fixtures"
DEFAULT_OUTPUT = ROOT / "data" / "outputs" / "debug_reconciliacion_hermes.xlsx"
DEFAULT_INVENTORY_PATTERN = "INVENTARIOS*.xlsx"
DEFAULT_REQUIREMENTS_PATTERN = "CONTROL*.xlsx"
DEFAULT_INVENTORY_DESCRIPTION = "Descripcion Larga"
DEFAULT_INVENTORY_CODE = "CODIGO"
DEFAULT_INVENTORY_QUANTITY = "CANT"
DEFAULT_REQUIREMENTS_DESCRIPTION = "DESCRIPCION DEL MATERIAL"
DEFAULT_REQUIREMENTS_QUANTITY = "CANTIDAD TOTAL"


def _require_columns(dataframe: pd.DataFrame, columns: tuple[str, ...]) -> None:
    missing = [column for column in columns if column not in dataframe.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")


def export_debug_report(
    inventory_path: Path,
    requirements_path: Path,
    output_path: Path,
    inventory_description: str,
    inventory_code: str,
    inventory_quantity: str,
    requirements_description: str,
    requirements_quantity: str,
) -> None:
    inventory = pd.read_excel(inventory_path, engine="openpyxl")
    requirements = pd.read_excel(requirements_path, engine="openpyxl")
    _require_columns(
        inventory,
        (inventory_description, inventory_code, inventory_quantity),
    )
    _require_columns(
        requirements,
        (requirements_description, requirements_quantity),
    )

    state = HermesState()
    state.set_dataset(
        LoadedDataset(DataSource.INVENTORY, inventory_path, inventory)
    )
    state.set_dataset(
        LoadedDataset(DataSource.REQUIREMENTS, requirements_path, requirements)
    )
    for key, column in {
        "inventory_description": inventory_description,
        "inventory_code": inventory_code,
        "inventory_quantity": inventory_quantity,
        "requirements_description": requirements_description,
        "requirements_quantity": requirements_quantity,
    }.items():
        state.set_mapping(key, column)

    report = ReconciliationService().reconcile(state)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        pd.DataFrame(
            [
                ("Resumen", report.build_summary()),
                ("Filas de cruce", len(report.matches)),
                ("Requerimientos segmentados", len(report.requirements)),
                ("Inventario segmentado", len(report.inventory)),
            ],
            columns=["Campo", "Valor"],
        ).to_excel(writer, sheet_name="Resumen", index=False)
        report.matches.to_excel(writer, sheet_name="Cruce", index=False)
        report.requirements.to_excel(
            writer,
            sheet_name="Req segmentados",
            index=False,
        )
        report.inventory.to_excel(
            writer,
            sheet_name="Inv segmentado",
            index=False,
        )


def _default_fixture(pattern: str, label: str) -> Path:
    matches = sorted(DEFAULT_FIXTURES_DIR.glob(pattern))
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(
            f"No {label} file found in {DEFAULT_FIXTURES_DIR} "
            f"matching {pattern!r}."
        )
    options = ", ".join(path.name for path in matches)
    raise ValueError(
        f"Multiple {label} files found in {DEFAULT_FIXTURES_DIR}: {options}. "
        "Pass the desired path explicitly."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export detailed Hermes reconciliation tables.",
    )
    parser.add_argument(
        "inventory",
        nargs="?",
        type=Path,
        default=None,
        help="Inventory .xlsx path.",
    )
    parser.add_argument(
        "requirements",
        nargs="?",
        type=Path,
        default=None,
        help="Requirements .xlsx path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output .xlsx path.",
    )
    parser.add_argument(
        "--inventory-description",
        default=DEFAULT_INVENTORY_DESCRIPTION,
    )
    parser.add_argument("--inventory-code", default=DEFAULT_INVENTORY_CODE)
    parser.add_argument(
        "--inventory-quantity",
        default=DEFAULT_INVENTORY_QUANTITY,
    )
    parser.add_argument(
        "--requirements-description",
        default=DEFAULT_REQUIREMENTS_DESCRIPTION,
    )
    parser.add_argument(
        "--requirements-quantity",
        default=DEFAULT_REQUIREMENTS_QUANTITY,
    )
    args = parser.parse_args()
    if (args.inventory is None) != (args.requirements is None):
        parser.error("Pass both inventory and requirements paths, or neither.")
    if args.inventory is None:
        args.inventory = _default_fixture(
            DEFAULT_INVENTORY_PATTERN,
            "inventory",
        )
        args.requirements = _default_fixture(
            DEFAULT_REQUIREMENTS_PATTERN,
            "requirements",
        )
    return args


def main() -> int:
    args = parse_args()
    export_debug_report(
        inventory_path=args.inventory,
        requirements_path=args.requirements,
        output_path=args.output,
        inventory_description=args.inventory_description,
        inventory_code=args.inventory_code,
        inventory_quantity=args.inventory_quantity,
        requirements_description=args.requirements_description,
        requirements_quantity=args.requirements_quantity,
    )
    print(f"Exported debug reconciliation report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
