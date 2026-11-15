from __future__ import annotations

from pathlib import Path

import pdfplumber

from pdf_stand.models import ParseError, ParseResult, TableResult


def _cell(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


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
    try:
        with pdfplumber.open(source) as pdf:
            pages = len(pdf.pages)
            for index, page in enumerate(pdf.pages, start=1):
                extracted = page.extract_tables() or []
                for raw in extracted:
                    rows = [[_cell(c) for c in row] for row in raw]
                    # drop fully empty rows
                    rows = [r for r in rows if any(c not in (None, "") for c in r)]
                    if rows:
                        tables.append(TableResult(page=index, rows=rows))
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
            errors=[ParseError("no_tables", "no tables extracted")],
            engine=engine,
        )

    return ParseResult(ok=True, pages=pages, tables=tables, errors=[], engine=engine)
