from pathlib import Path

from pdf_stand.layout import build_grid, font_family, snap_font_size, style_from_chars
from pdf_stand.pipeline import parse_file


def test_font_size_matches_reference_rounding():
    assert snap_font_size(8.64) == 8.5
    assert snap_font_size(6.84) == 6.5
    assert font_family("HPDFAB+Arial-BoldMTBold") == "Arial"
    assert font_family("Helvetica-Bold") == "Helvetica"


def test_payment_block_cell_merges_across_two_rows():
    bank = (
        (0, 0, 100, 30),
        "ПАО Сбербанк",
        {"size": 8.5, "bold": False, "font": "Arial", "valign": "top", "halign": "left", "wrap": True},
    )
    bik = (
        (100, 0, 140, 12),
        "БИК",
        {"size": 8.5, "bold": False, "font": "Arial", "valign": "top", "halign": "left", "wrap": False},
    )
    account = (
        (100, 12, 140, 30),
        "Сч. №",
        {"size": 8.5, "bold": False, "font": "Arial", "valign": "top", "halign": "left", "wrap": False},
    )
    grid = build_grid([bank, bik, account])
    assert grid["rows"][0][0] == "ПАО Сбербанк"
    assert grid["rows"][0][1] == "БИК"
    assert grid["rows"][1][1] == "Сч. №"
    assert "A1:A2" in grid["merges"]
    assert grid["row_heights_pt"] == [12.0, 18.0]


def test_equal_padding_is_center_and_top_hugging_text_is_top():
    centered = style_from_chars(
        [{"x0": 10, "x1": 30, "top": 4.9, "bottom": 13.9, "size": 9, "fontname": "Arial", "text": "Name"}],
        (0, 0, 40, 18),
    )
    assert centered["valign"] == "center"
    assert centered["size"] == 9
    goods = style_from_chars(
        [{"x0": 2, "x1": 20, "top": 1.2, "bottom": 8.1, "size": 6.84, "fontname": "Arial-BoldMT", "text": "№"}],
        (0, 0, 30, 9),
    )
    assert goods["valign"] == "top"
    assert goods["size"] == 6.5
    assert goods["bold"] is True
    assert goods["font"] == "Arial"


def test_invoice_sheets_include_page_images():
    src = Path.home() / "Downloads/pdfexel-2026-11-16/счет Резиденция детства 05.11 (1).pdf"
    if not src.exists():
        return
    result = parse_file(src)
    assert result.ok
    assert len(result.sheets) >= 2
    imgs0 = result.sheets[0].get("images") or []
    imgs1 = result.sheets[1].get("images") or []
    assert len(imgs0) == 2
    assert len(imgs1) == 1
    logo, qr = imgs0
    assert abs(logo["width_pt"] - 184.44) < 1
    assert abs(logo["height_pt"] - 36.72) < 1
    assert abs(qr["width_pt"] - 97.56) < 1
    assert abs(qr["height_pt"] - 97.56) < 1
    assert logo["mime"] == "image/png"
    assert len(logo["data_b64"]) > 100
