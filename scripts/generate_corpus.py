#!/usr/bin/env python3
"""Generate 20 pass PDFs + golden JSON + manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
PASS = ROOT / "tests" / "corpus" / "pass"
EXPECTED = ROOT / "tests" / "corpus" / "expected"
MANIFEST = ROOT / "tests" / "corpus" / "manifest.json"

_FONT_CANDIDATES = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
]


def _register_fonts() -> tuple[str, str]:
    for path in _FONT_CANDIDATES:
        if path.exists():
            pdfmetrics.registerFont(TTFont("CorpusSans", str(path)))
            return "CorpusSans", "CorpusSans"
    return "Helvetica", "Helvetica-Bold"


FONT, FONT_BOLD = _register_fonts()


def style_grid(data: list[list[object]]) -> Table:
    t = Table(data, hAlign="LEFT")
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.85, 0.85, 0.85)),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return t


def write_pdf(name: str, flowables: list, *, pagesize=A4) -> Path:
    path = PASS / name
    doc = SimpleDocTemplate(str(path), pagesize=pagesize, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    doc.build(flowables)
    print("wrote", path.relative_to(ROOT))
    return path


def main() -> int:
    PASS.mkdir(parents=True, exist_ok=True)
    EXPECTED.mkdir(parents=True, exist_ok=True)

    write_pdf(
        "01_simple.pdf",
        [style_grid([["Name", "Qty", "Price"], ["Apple", "3", "1.5"], ["Banana", "5", "0.8"], ["Cherry", "2", "3.2"]])],
    )
    write_pdf(
        "02_two_tables.pdf",
        [
            style_grid([["A", "B"], ["1", "2"]]),
            Spacer(1, 24),
            style_grid([["SKU", "Stock"], ["X1", "100"], ["X2", "50"]]),
        ],
    )
    write_pdf(
        "03_wide.pdf",
        [style_grid([[f"Col{i}" for i in range(1, 9)], [str(i) for i in range(1, 9)]])],
        pagesize=landscape(A4),
    )
    write_pdf(
        "04_tall.pdf",
        [style_grid([["id", "value"]] + [[str(i), str(i * 1.5)] for i in range(1, 26)])],
    )
    write_pdf(
        "05_russian.pdf",
        [style_grid([["Товар", "Кол", "Цена"], ["Яблоки", "10", "120.5"], ["Молоко", "2", "89"]])],
    )
    write_pdf(
        "06_numbers.pdf",
        [style_grid([["Number", "Percent", "Currency"], ["1234.56", "15%", "$99.99"]])],
    )
    write_pdf(
        "07_empty_cells.pdf",
        [style_grid([["A", "B", "C"], ["x", "", "z"], ["", "y", ""]])],
    )
    write_pdf(
        "08_invoice.pdf",
        [
            Paragraph("Invoice INV-001", getSampleStyleSheet()["Heading2"]),
            Spacer(1, 12),
            style_grid(
                [
                    ["Item", "Qty", "Amount"],
                    ["Service A", "1", "1000"],
                    ["Service B", "2", "500"],
                    ["Total", "", "2000"],
                ]
            ),
        ],
    )
    write_pdf(
        "09_dates.pdf",
        [style_grid([["Date", "Event"], ["2026-11-14", "Launch"], ["2026-12-01", "Review"]])],
    )
    write_pdf(
        "10_styled_header.pdf",
        [style_grid([["Product", "Score"], ["Alpha", "9"], ["Beta", "7"]])],
    )
    write_pdf(
        "11_cities.pdf",
        [style_grid([["City", "Pop", "Region"], ["Moscow", "12", "C"], ["SPb", "5", "NW"], ["Kazan", "1", "V"]])],
    )
    write_pdf(
        "12_links_like.pdf",
        [style_grid([["Label", "URL"], ["Docs", "https://example.com"], ["Home", "https://example.org"]])],
    )
    write_pdf(
        "13_mixed.pdf",
        [style_grid([["Label", "Amount", "Note"], ["total", "1000.00", "ok"], ["rate", "25.50%", "quarter"]])],
    )
    write_pdf(
        "14_single_row.pdf",
        [style_grid([["Only", "Header"], ["one", "row"]])],
    )
    write_pdf(
        "15_inventory.pdf",
        [style_grid([["SKU", "Name", "Qty"], ["A-1", "Bolt", "100"], ["A-2", "Nut", "200"], ["B-1", "Washer", "500"]])],
    )
    # two pages
    write_pdf(
        "16_multipage.pdf",
        [
            style_grid([["Page", "Item"], ["1", "First"]]),
            PageBreak(),
            style_grid([["Page", "Item"], ["2", "Second"], ["2", "Third"]]),
        ],
    )
    write_pdf(
        "17_budget.pdf",
        [style_grid([["Category", "Plan", "Fact"], ["Dev", "100", "90"], ["Ops", "50", "55"], ["Sales", "200", "180"]])],
    )
    write_pdf(
        "18_employees.pdf",
        [style_grid([["Name", "Role"], ["Ann", "Eng"], ["Bob", "PM"], ["Cid", "QA"]])],
    )
    write_pdf(
        "19_metrics.pdf",
        [style_grid([["Metric", "Value"], ["CTR", "2.1%"], ["CR", "0.8%"], ["ARPU", "12.5"]])],
    )
    write_pdf(
        "20_orders.pdf",
        [style_grid([["Order", "Status", "Sum"], ["1001", "paid", "10"], ["1002", "new", "20"], ["1003", "paid", "15"]])],
    )

    # Import after PDFs exist
    sys.path.insert(0, str(ROOT))
    from pdf_stand.pipeline import parse_file

    entries = []
    for path in sorted(PASS.glob("*.pdf")):
        result = parse_file(path)
        if not result.ok:
            print("FAIL generate golden", path.name, result.to_dict(), file=sys.stderr)
            return 1
        golden = {"tables": result.stable_tables()}
        out = EXPECTED / f"{path.stem}.json"
        out.write_text(json.dumps(golden, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote", out.relative_to(ROOT))
        entries.append({"id": path.stem.split("_", 1)[0], "file": path.name, "expect": "pass", "min_tables": 1})

    MANIFEST.write_text(json.dumps({"pass": entries}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", MANIFEST.relative_to(ROOT), "count", len(entries))
    return 0 if len(entries) == 20 else 1


if __name__ == "__main__":
    raise SystemExit(main())
