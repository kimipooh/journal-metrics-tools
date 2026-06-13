#!/usr/bin/env python3
"""Journal Metrics Workflow CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

from journal_mapper import row_to_journal_values
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet


MAIN_HEADERS = [
    "id",
    "name",
    "o_name",
    "issn",
    "eissn",
    "journal_name",
    "note",
    "status",
]

JOURNAL_HEADERS = [
    "main_row_id",
    "journal_type",
    "external_journal_id",
    "journal_name",
    "affiliation",
    "grade",
    "profile_url",
    "fetch_status",
    "fetched_at",
    "raw_json",
]

CONVERT_HEADERS = [
    "id",
    "journal_type",
    "grade",
    "external_journal_id",
    "profile_url",
    "journal_name",
    "affiliation",
    "note",
    "convert_status",
]

README_ROWS = [
    ("Section", "Description"),
    ("Purpose", "Journal Metrics Workflow Phase 1 template workbook."),
    ("Usage", "python journal_metrics.py template --output journal_metrics.xlsx"),
    ("main", "Human-edited input sheet. The status column is created but not processed automatically."),
    ("journal", "Placeholder for fetched journal candidates in later phases."),
    ("convert", "Placeholder for confirmed rows prepared for later export or database import."),
    ("Phase 1 limits", "No external CLI, database, adapter, fetch-journal, convert, or enrich-db is called."),
]

DEFAULT_WIDTH = 14
MIN_WIDTH_PADDING = 2
MAX_WIDTH = 48


def apply_header_style(ws: Worksheet) -> None:
    for cell in ws[1]:
        cell.font = Font(bold=True)
    ws.freeze_panes = "A2"


def set_reasonable_widths(ws: Worksheet, rows: Iterable[Sequence[object]]) -> None:
    widths: dict[int, int] = {}
    for row in rows:
        for index, value in enumerate(row, start=1):
            width = len(str(value)) + MIN_WIDTH_PADDING if value is not None else DEFAULT_WIDTH
            widths[index] = max(widths.get(index, DEFAULT_WIDTH), width)

    for index, width in widths.items():
        ws.column_dimensions[get_column_letter(index)].width = min(width, MAX_WIDTH)


def write_rows(ws: Worksheet, rows: Sequence[Sequence[object]]) -> None:
    for row in rows:
        ws.append(row)
    apply_header_style(ws)
    set_reasonable_widths(ws, rows)


def write_header_sheet(ws: Worksheet, headers: Sequence[str]) -> None:
    write_rows(ws, [headers])


def append_journal_rows(
    ws: Worksheet,
    rows: list[dict],
    headers: list[str],
) -> int:
    for row in rows:
        ws.append(row_to_journal_values(row, headers))
    return len(rows)


def build_template_workbook() -> Workbook:
    wb = Workbook()

    readme = wb.active
    readme.title = "README"
    write_rows(readme, README_ROWS)

    main = wb.create_sheet("main")
    write_header_sheet(main, MAIN_HEADERS)

    journal = wb.create_sheet("journal")
    write_header_sheet(journal, JOURNAL_HEADERS)

    convert = wb.create_sheet("convert")
    write_header_sheet(convert, CONVERT_HEADERS)

    return wb


def template_command(args: argparse.Namespace) -> None:
    output_path = Path(args.output)
    wb = build_template_workbook()
    wb.save(output_path)
    print(f"Created template workbook: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Journal Metrics Workflow tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    template = subparsers.add_parser(
        "template",
        help="Create a Phase 1 Journal Metrics template workbook.",
    )
    template.add_argument(
        "--output",
        required=True,
        help="Output .xlsx path. Existing files are overwritten.",
    )
    template.set_defaults(func=template_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
