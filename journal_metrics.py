#!/usr/bin/env python3
"""Journal Metrics Workflow CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Sequence

from adapters.mock import fetch_journal as fetch_mock_journal
from journal_mapper import map_envelope_to_journal_rows
from journal_mapper import row_to_journal_values
from openpyxl import Workbook, load_workbook
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

MAIN_STATUS_BY_ENVELOPE_STATUS = {
    "fetched": "fetched",
    "multiple_candidates": "multiple_candidates",
    "not_found": "not_found",
    "adapter_error": "adapter_error",
}

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


def header_index(ws: Worksheet) -> dict[str, int]:
    return {
        str(cell.value): index
        for index, cell in enumerate(ws[1])
        if cell.value is not None
    }


def cell_value(row: Sequence[object], index: dict[str, int], header: str) -> object:
    column_index = index.get(header)
    if column_index is None:
        return None
    if column_index >= len(row):
        return None
    return row[column_index].value


def text_value(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


def fetch_journal_command(args: argparse.Namespace) -> None:
    if args.adapter != "mock":
        raise ValueError("Phase 2D only supports --adapter mock")

    input_path = Path(args.input)
    wb = load_workbook(input_path)
    if "main" not in wb.sheetnames:
        raise ValueError("Workbook does not contain a main sheet")
    if "journal" not in wb.sheetnames:
        raise ValueError("Workbook does not contain a journal sheet")

    main_ws = wb["main"]
    journal_ws = wb["journal"]
    main_headers = header_index(main_ws)

    for required_header in ["status", "journal_name", "name"]:
        if required_header not in main_headers:
            raise ValueError(f"main sheet is missing required header: {required_header}")

    processed_rows = 0
    appended_rows = 0

    for excel_row_number, row in enumerate(
        main_ws.iter_rows(min_row=2),
        start=2,
    ):
        status = text_value(cell_value(row, main_headers, "status")).lower()
        if status not in {"", "pending"}:
            continue

        query = text_value(cell_value(row, main_headers, "journal_name"))
        if not query:
            query = text_value(cell_value(row, main_headers, "name"))
        if not query:
            continue

        envelope = fetch_mock_journal(query)
        journal_rows = map_envelope_to_journal_rows(
            envelope,
            main_row_id=excel_row_number,
        )
        appended_rows += append_journal_rows(
            journal_ws,
            journal_rows,
            JOURNAL_HEADERS,
        )
        main_ws.cell(
            row=excel_row_number,
            column=main_headers["status"] + 1,
            value=MAIN_STATUS_BY_ENVELOPE_STATUS[envelope["status"]],
        )
        processed_rows += 1

    wb.save(input_path)
    print(f"Processed main rows: {processed_rows}")
    print(f"Appended journal rows: {appended_rows}")
    print(f"Adapter: {args.adapter}")


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

    fetch_journal = subparsers.add_parser(
        "fetch-journal",
        help="Fetch journal candidates into the journal sheet.",
    )
    fetch_journal.add_argument(
        "--input",
        required=True,
        help="Input .xlsx path to update in place.",
    )
    fetch_journal.add_argument(
        "--adapter",
        required=True,
        choices=["mock"],
        help="Adapter to use. Phase 2D supports only mock.",
    )
    fetch_journal.set_defaults(func=fetch_journal_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
