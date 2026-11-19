"""Heuristics: is this PDF mostly a raster scan (photo/scan of paper)?"""

from __future__ import annotations

from typing import Any


def _page_image_cover(page: Any) -> float:
    width = float(getattr(page, "width", 0) or 0)
    height = float(getattr(page, "height", 0) or 0)
    area = width * height
    if area <= 0:
        return 0.0
    images = getattr(page, "images", None) or []
    covered = 0.0
    for image in images:
        x0 = float(image.get("x0", 0) or 0)
        x1 = float(image.get("x1", x0) or x0)
        top = float(image.get("top", 0) or 0)
        bottom = float(image.get("bottom", top) or top)
        covered += max(0.0, x1 - x0) * max(0.0, bottom - top)
    return min(1.0, covered / area)


def _meaningful_words(page: Any) -> int:
    words = page.extract_words() or []
    count = 0
    for word in words:
        text = str(word.get("text") or "").strip()
        if len(text) >= 3 and any(ch.isalpha() for ch in text):
            count += 1
    return count


def detect_scanned_pdf(pdf: Any, *, max_pages: int = 3) -> bool:
    """True when sampled pages are dominated by full-page raster images.

    Vector PDFs with a small logo/stamp stay False. Scan/photo PDFs (УПД, КС-2)
    with a page-sized image return True even if a noisy OCR text layer exists.
    """
    pages = list(getattr(pdf, "pages", []) or [])
    if not pages:
        return False
    sample = pages[: max(1, max_pages)]
    covers = [_page_image_cover(page) for page in sample]
    words = [_meaningful_words(page) for page in sample]
    avg_cover = sum(covers) / len(covers)
    # Strong: almost full-page image on a sampled page.
    if any(c >= 0.85 for c in covers):
        return True
    # Weaker: high average cover and little real text.
    if avg_cover >= 0.65 and sum(words) < 40:
        return True
    return False
