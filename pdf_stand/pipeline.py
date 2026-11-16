from __future__ import annotations

from pathlib import Path

import pdfplumber

from pdf_stand.layout import sheet_from_page
from pdf_stand.models import ParseError, ParseResult, TableResult


def _cell(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _column_widths_pt(table: pdfplumber.table.Table) -> list[float]:
    widths: list[float] = []
    for column in table.columns:
        cells = [cell for cell in column.cells if cell is not None]
        if not cells:
            widths.append(0.0)
            continue
        x0 = min(cell[0] for cell in cells)
        x1 = max(cell[2] for cell in cells)
        widths.append(round(x1 - x0, 2))
    return widths


def _row_heights_pt(table: pdfplumber.table.Table) -> list[float]:
    heights: list[float] = []
    for row in table.rows:
        cells = [cell for cell in row.cells if cell is not None]
        if not cells:
            heights.append(0.0)
            continue
        top = min(cell[1] for cell in cells)
        bottom = max(cell[3] for cell in cells)
        heights.append(round(bottom - top, 2))
    return heights


def parse_file(path: Path | str) -> ParseResult:
    source = Path(path)
    engine = {"pdfplumber_version": getattr(pdfplumber, "__version__", None)}

    if not source.exists():
        return ParseResult(
            ok=False,
            errors=[ParseError("not_found", f"file not found: {source}")],
            engine=engine,
        )
    if source.suffix.lower() != ".pdf":
        return ParseResult(
            ok=False,
            errors=[ParseError("unsupported_format", f"expected .pdf, got {source.suffix}")],
            engine=engine,
        )

    tables: list[TableResult] = []
    sheets: list[dict] = []
    try:
        with pdfplumber.open(source) as pdf:
            pages = len(pdf.pages)
            for index, page in enumerate(pdf.pages, start=1):
                found_tables = page.find_tables() or []
                sheet = sheet_from_page(page, found_tables)
                if sheet is not None:
                    sheet["page"] = index
                    sheets.append(sheet)
                for found in found_tables:
                    raw_rows = found.extract() or []
                    heights = _row_heights_pt(found)
                    rows: list[list[str | None]] = []
                    kept_heights: list[float] = []
                    for raw, height in zip(raw_rows, heights):
                        cleaned = [_cell(c) for c in raw]
                        if any(c not in (None, "") for c in cleaned):
                            rows.append(cleaned)
                            kept_heights.append(height)
                    if rows:
                        tables.append(
                            TableResult(
                                page=index,
                                rows=rows,
                                col_widths_pt=_column_widths_pt(found),
                                row_heights_pt=kept_heights,
                            )
                        )
    except Exception as exc:  # noqa: BLE001
        return ParseResult(
            ok=False,
            errors=[ParseError("parse_fail", str(exc))],
            engine=engine,
        )

    if not tables:
        return ParseResult(
            ok=False,
            pages=pages if "pages" in locals() else 0,
            tables=[],
            sheets=sheets,
            errors=[ParseError("no_tables", "no tables extracted")],
            engine=engine,
        )

    return ParseResult(ok=True, pages=pages, tables=tables, sheets=sheets, errors=[], engine=engine)
