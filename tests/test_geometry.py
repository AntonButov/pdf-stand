from pathlib import Path

from pdf_stand.pipeline import parse_file

ROOT = Path(__file__).resolve().parents[1]
SIMPLE = ROOT / "tests" / "corpus" / "pass" / "01_simple.pdf"


def test_column_and_row_sizes_match_pdf_points():
    result = parse_file(SIMPLE)
    assert result.ok
    table = result.tables[0]
    assert table.col_widths_pt == [43.03, 26.0, 32.5]
    assert table.row_heights_pt == [18.0, 18.0, 18.0, 18.0]
    assert table.to_dict()["col_widths_pt"] == [43.03, 26.0, 32.5]
    assert table.to_dict()["row_heights_pt"] == [18.0, 18.0, 18.0, 18.0]
