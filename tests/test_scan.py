from pathlib import Path

from pdf_stand.pipeline import parse_file
from pdf_stand.scan import detect_scanned_pdf

FIXTURE_VECTOR = Path(__file__).parent / "fixtures" / "stamp_sig_smask.pdf"
FIXTURE_SIMPLE = Path(__file__).parent / "corpus" / "pass" / "01_simple.pdf"
SCAN_UPD = Path("/tmp/pdfexel-fails/upd12.pdf")
SCAN_KS2 = Path("/tmp/pdfexel-fails/ks2.pdf")


def test_vector_simple_not_scanned():
    result = parse_file(FIXTURE_SIMPLE)
    assert result.ok
    assert result.scanned is False


def test_fixture_stamp_pdf_not_full_page_scan():
    # Small embedded stamp images must not trip the scan detector.
    import pdfplumber

    with pdfplumber.open(FIXTURE_VECTOR) as pdf:
        assert detect_scanned_pdf(pdf) is False


def test_scan_upd_detected_when_present():
    if not SCAN_UPD.exists():
        return
    result = parse_file(SCAN_UPD)
    assert result.scanned is True
    assert result.ok is False
    assert result.errors and result.errors[0].code == "scanned_pdf"


def test_scan_ks2_detected_when_present():
    if not SCAN_KS2.exists():
        return
    result = parse_file(SCAN_KS2)
    assert result.scanned is True
    assert result.ok is False
    assert any(e.code == "scanned_pdf" for e in result.errors)
