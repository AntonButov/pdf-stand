"""Stamps/signatures with PDF soft masks must not keep a black plate."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

from pdf_stand.layout import extract_page_images
from pdf_stand.pipeline import parse_file

FIXTURE = Path(__file__).parent / "fixtures" / "stamp_sig_smask.pdf"
MONTAGE = Path(
    "/tmp/pdfexel-today/all/ok_78d1cf03a152_c72736673052__Монтаж СПС мастерские ИГФ_ 26-3.pdf"
)


def _png_from_b64(data_b64: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(data_b64))).convert("RGB")


def _black_ratio(img: Image.Image, threshold: int = 40) -> float:
    rgb = img.convert("RGB")
    pixels = list(rgb.getdata())
    if not pixels:
        return 1.0
    black = sum(1 for r, g, b in pixels if r < threshold and g < threshold and b < threshold)
    return black / len(pixels)


def _find_soffice() -> str | None:
    import shutil
    from pathlib import Path

    mac = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
    if mac.exists():
        return str(mac)
    return shutil.which("soffice") or shutil.which("libreoffice")


def test_fixture_xlsx_screenshot_has_no_black_plate(tmp_path: Path):
    """Round-trip fixture → json-stand xlsx → LibreOffice PNG; black plate must be gone."""
    import sys

    soffice = _find_soffice()
    if not soffice:
        return
    json_stand_root = Path(__file__).resolve().parents[2] / "json-stand"
    if json_stand_root.is_dir():
        sys.path.insert(0, str(json_stand_root))
    try:
        import pymupdf
        from json_stand.pipeline import convert_data
    except ImportError:
        return

    result = parse_file(FIXTURE)
    assert result.sheets
    xlsx = tmp_path / "stamp_sig.xlsx"
    convert_data({"sheets": result.sheets}, xlsx, normalize=True)

    work = tmp_path / "lo"
    work.mkdir()
    src = work / "input.xlsx"
    src.write_bytes(xlsx.read_bytes())
    import subprocess

    proc = subprocess.run(
        [
            soffice,
            f"-env:UserInstallation=file://{work / 'profile'}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(work),
            str(src),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    pdfs = list(work.glob("*.pdf"))
    assert pdfs, (proc.stderr or proc.stdout or "libreoffice produced no pdf")[:400]
    doc = pymupdf.open(pdfs[0])
    try:
        pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1.2, 1.2), alpha=False)
        shot = tmp_path / "shot.png"
        pix.save(shot)
    finally:
        doc.close()
    ratio = _black_ratio(Image.open(shot))
    assert ratio < 0.05, f"screenshot still has black plate: ratio={ratio:.4f}"


def test_fixture_smask_images_flatten_onto_white():
    assert FIXTURE.exists(), f"missing fixture {FIXTURE}"
    result = parse_file(FIXTURE)
    # Fixture is image-only (no table grid) — sheets still carry embeds.
    assert result.sheets, f"expected sheets, errors={result.errors}"
    images = result.sheets[0].get("images") or []
    assert len(images) >= 2, f"expected stamp+sig, got {len(images)}"
    for image in images:
        pil = _png_from_b64(image["data_b64"])
        ratio = _black_ratio(pil)
        assert ratio < 0.15, f"black plate still present: ratio={ratio:.3f} size={pil.size}"


def test_extract_page_images_applies_smask(monkeypatch):
    """Direct layout check: decoded PNGs are mostly non-black."""
    import pdfplumber

    with pdfplumber.open(FIXTURE) as doc:
        page = doc.pages[0]
        images = extract_page_images(page)
    assert len(images) >= 2
    for image in images:
        pil = _png_from_b64(image["data_b64"])
        assert _black_ratio(pil) < 0.15


def test_montage_stamp_and_signature_not_black_plate():
    if not MONTAGE.exists():
        return
    result = parse_file(MONTAGE)
    assert result.ok, result.errors
    images = result.sheets[0].get("images") or []
    assert len(images) >= 2
    for image in images:
        pil = _png_from_b64(image["data_b64"])
        # Real stamp/sig: ink is a small fraction; plate must not dominate.
        assert _black_ratio(pil) < 0.35, f"montage image still black-heavy: {_black_ratio(pil):.3f}"
