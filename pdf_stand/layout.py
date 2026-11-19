from __future__ import annotations

import base64
import io
import math
import re
from collections import Counter
from typing import Any

EDGE_TOL = 1.25

_FONT_SUFFIX = re.compile(
    r"[-,]?(BoldMTBold|BoldItalicMT|BoldMT|Bold|Italic|Oblique|UnicodeMS|MT|PS)+$"
)


def snap_font_size(size: float) -> float:
    """Match the reference workbook: 8.64 -> 8.5, 6.84 -> 6.5."""
    return math.floor(size * 2 + 1e-6) / 2


def font_family(fontname: str) -> str:
    name = fontname.split("+")[-1]
    previous = None
    while name and name != previous:
        previous = name
        name = _FONT_SUFFIX.sub("", name)
    return name.replace("-", "").strip() or "Arial"


def cluster_edges(values: list[float], tol: float = EDGE_TOL) -> list[float]:
    if not values:
        return []
    ordered = sorted(values)
    groups: list[list[float]] = [[ordered[0]]]
    for value in ordered[1:]:
        if value - groups[-1][-1] <= tol:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [round(sum(group) / len(group), 2) for group in groups]


def _nearest(edges: list[float], value: float) -> int:
    return min(range(len(edges)), key=lambda index: abs(edges[index] - value))


def _span(edges: list[float], start: float, end: float) -> tuple[int, int]:
    i0 = _nearest(edges, start)
    i1 = _nearest(edges, end)
    if i1 <= i0:
        i1 = min(i0 + 1, len(edges) - 1)
    return i0, i1


def _chars_in_box(chars: list[dict[str, Any]], box: tuple[float, float, float, float]) -> list[dict[str, Any]]:
    x0, top, x1, bottom = box
    found = []
    for char in chars:
        mid_x = (char["x0"] + char["x1"]) / 2
        mid_y = (char["top"] + char["bottom"]) / 2
        if x0 - 0.5 <= mid_x < x1 + 0.5 and top - 0.5 <= mid_y < bottom + 0.5:
            found.append(char)
    return found


def text_from_chars(chars: list[dict[str, Any]]) -> str:
    if not chars:
        return ""
    ordered = sorted(chars, key=lambda char: (round(char["top"], 1), char["x0"]))
    lines: list[list[dict[str, Any]]] = []
    current_top: float | None = None
    for char in ordered:
        if current_top is None or abs(char["top"] - current_top) > 1.6:
            lines.append([char])
            current_top = char["top"]
        else:
            lines[-1].append(char)
    parts: list[str] = []
    for line in lines:
        line = sorted(line, key=lambda char: char["x0"])
        text = ""
        previous = None
        for char in line:
            if previous is not None and char["x0"] - previous["x1"] > max(previous.get("size", 6) * 0.35, 1.2):
                text += " "
            text += char.get("text") or ""
            previous = char
        cleaned = text.strip()
        if cleaned:
            parts.append(cleaned)
    return "\n".join(parts)


def style_from_chars(chars: list[dict[str, Any]], box: tuple[float, float, float, float]) -> dict[str, Any]:
    x0, top, x1, bottom = box
    sizes = Counter(round(float(char["size"]), 2) for char in chars)
    names = Counter(str(char["fontname"]) for char in chars)
    size = sizes.most_common(1)[0][0]
    fontname = names.most_common(1)[0][0]
    text_x0 = min(float(char["x0"]) for char in chars)
    text_x1 = max(float(char["x1"]) for char in chars)
    text_top = min(float(char["top"]) for char in chars)
    text_bottom = max(float(char["bottom"]) for char in chars)
    pad_left = text_x0 - x0
    pad_right = x1 - text_x1
    pad_top = text_top - top
    pad_bottom = bottom - text_bottom
    if pad_right + 1.5 < pad_left and pad_right < 4:
        halign = "right"
    elif abs(pad_left - pad_right) <= 2 and min(pad_left, pad_right) > 4:
        halign = "center"
    else:
        halign = "left"
    if pad_top <= pad_bottom + 0.5:
        valign = "top"
    elif pad_bottom + 1 < pad_top:
        valign = "bottom"
    else:
        valign = "center"
    text = text_from_chars(chars)
    wrap = "\n" in text or (text_bottom - text_top) > size * 1.35
    return {
        "size": snap_font_size(size),
        "bold": "Bold" in fontname or "bold" in fontname,
        "font": font_family(fontname),
        "halign": halign,
        "valign": valign,
        "wrap": wrap,
    }


def _column_letter(index: int) -> str:
    """1-based column index to Excel letters. 1 -> A, 27 -> AA."""
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _merge_ref(col0: int, row0: int, col1: int, row1: int) -> str | None:
    if col1 == col0 and row1 == row0:
        return None
    start = f"{_column_letter(col0 + 1)}{row0 + 1}"
    end = f"{_column_letter(col1 + 1)}{row1 + 1}"
    return f"{start}:{end}"


def build_grid(
    boxes: list[tuple[tuple[float, float, float, float], str, dict[str, Any] | None]],
) -> dict[str, Any]:
    """Place boxes on one snapped grid. A box that covers several bands becomes a merge."""
    empty: dict[str, Any] = {
        "rows": [],
        "col_widths_pt": [],
        "row_heights_pt": [],
        "merges": [],
        "cell_styles": [],
    }
    if not boxes:
        return empty
    xs = cluster_edges([value for box, _, _ in boxes for value in (box[0], box[2])])
    ys = cluster_edges([value for box, _, _ in boxes for value in (box[1], box[3])])
    if len(xs) < 2 or len(ys) < 2:
        return empty
    cols = len(xs) - 1
    rows_n = len(ys) - 1
    texts: dict[tuple[int, int], str] = {}
    styles: dict[tuple[int, int], dict[str, Any]] = {}
    merges: list[str] = []
    taken: set[tuple[int, int]] = set()
    ordered = sorted(boxes, key=lambda item: (item[0][1], item[0][0], -(item[0][2] - item[0][0])))
    for box, text, style in ordered:
        c0, c1 = _span(xs, box[0], box[2])
        r0, r1 = _span(ys, box[1], box[3])
        c1 -= 1
        r1 -= 1
        slots = [(row, col) for row in range(r0, r1 + 1) for col in range(c0, c1 + 1)]
        if any(slot in taken for slot in slots):
            if (r0, c0) in taken or not text:
                continue
            slots = [(r0, c0)]
            c1, r1 = c0, r0
        taken.update(slots)
        ref = _merge_ref(c0, r0, c1, r1)
        if ref:
            merges.append(ref)
        texts[(r0, c0)] = text
        if style:
            styles[(r0, c0)] = style
    grid_rows: list[list[str | None]] = []
    grid_styles: list[list[dict[str, Any] | None]] = []
    for row_index in range(rows_n):
        row: list[str | None] = []
        style_row: list[dict[str, Any] | None] = []
        for col_index in range(cols):
            value = texts.get((row_index, col_index))
            row.append(value if value else None)
            style_row.append(styles.get((row_index, col_index)))
        grid_rows.append(row)
        grid_styles.append(style_row)
    return {
        "rows": grid_rows,
        "col_widths_pt": [round(xs[index + 1] - xs[index], 2) for index in range(cols)],
        "row_heights_pt": [round(ys[index + 1] - ys[index], 2) for index in range(rows_n)],
        "merges": merges,
        "cell_styles": grid_styles,
    }


def _decode_rgb_image(raw: bytes, width_px: int, height_px: int) -> Any:
    from PIL import Image

    if len(raw) == width_px * height_px * 3:
        return Image.frombytes("RGB", (width_px, height_px), raw)
    if len(raw) == width_px * height_px:
        return Image.frombytes("L", (width_px, height_px), raw).convert("RGB")
    return Image.open(io.BytesIO(raw)).convert("RGB")


def _mask_from_bits(raw: bytes, width: int, height: int, bits: int) -> Any:
    """Decode a DeviceGray soft-mask bitstream into an 8-bit L image."""
    from PIL import Image

    if bits == 8 and len(raw) >= width * height:
        return Image.frombytes("L", (width, height), raw[: width * height])
    if bits == 1:
        # Row stride is byte-aligned.
        row_bytes = (width + 7) // 8
        pixels = bytearray(width * height)
        for y in range(height):
            row = raw[y * row_bytes : (y + 1) * row_bytes]
            for x in range(width):
                byte = row[x // 8]
                bit = (byte >> (7 - (x % 8))) & 1
                pixels[y * width + x] = 255 if bit else 0
        return Image.frombytes("L", (width, height), bytes(pixels))
    if bits in (2, 4):
        pixels_per_byte = 8 // bits
        row_bytes = (width + pixels_per_byte - 1) // pixels_per_byte
        max_val = (1 << bits) - 1
        pixels = bytearray(width * height)
        for y in range(height):
            row = raw[y * row_bytes : (y + 1) * row_bytes]
            for x in range(width):
                byte = row[x // pixels_per_byte]
                shift = bits * (pixels_per_byte - 1 - (x % pixels_per_byte))
                val = (byte >> shift) & max_val
                pixels[y * width + x] = int(round(val * 255 / max_val))
        return Image.frombytes("L", (width, height), bytes(pixels))
    return Image.open(io.BytesIO(raw)).convert("L")


def _decode_soft_mask(stream: Any, width_px: int, height_px: int) -> Any | None:
    """Load PDF SMask as an L-mode alpha channel sized to the color image."""
    from pdfminer.pdftypes import resolve1
    from PIL import Image

    try:
        attrs = getattr(stream, "attrs", None) or {}
        smask_ref = attrs.get("SMask")
        if smask_ref is None:
            return None
        smask = resolve1(smask_ref)
        if smask is None:
            return None
        raw = smask.get_data()
        smask_attrs = getattr(smask, "attrs", None) or {}
        mw = int(smask_attrs.get("Width") or width_px)
        mh = int(smask_attrs.get("Height") or height_px)
        bits = int(smask_attrs.get("BitsPerComponent") or 8)
        if mw <= 0 or mh <= 0:
            return None
        mask = _mask_from_bits(raw, mw, mh, bits)
        if mask.size != (width_px, height_px):
            mask = mask.resize((width_px, height_px), Image.Resampling.BILINEAR)
        return mask
    except Exception:  # noqa: BLE001
        return None


def _composite_smask_on_white(rgb: Any, mask: Any, matte: list[float] | None = None) -> Any:
    """Apply soft-mask alpha and flatten onto white (fixes black stamp/signature boxes).

    - No Matte: colour is straight (non-premultiplied) → PIL paste over white.
    - Black Matte [0,0,0]: samples are premultiplied into black → `out = c' + white*(1-α)`.
    - Other Matte: recover straight colour, then paste over white.
    """
    from PIL import Image, ImageChops

    rgb = rgb.convert("RGB")
    mask = mask.convert("L")
    if mask.size != rgb.size:
        mask = mask.resize(rgb.size, Image.Resampling.BILINEAR)

    if matte is None:
        rgba = rgb.convert("RGBA")
        rgba.putalpha(mask)
        bg = Image.new("RGB", rgb.size, (255, 255, 255))
        bg.paste(rgba, mask=mask)
        return bg

    scale = 255.0 if max(float(x) for x in matte[:3]) <= 1.0 else 1.0
    matte_rgb = (float(matte[0]) * scale, float(matte[1]) * scale, float(matte[2]) * scale)
    if matte_rgb == (0.0, 0.0, 0.0):
        # Premultiplied against black: add residual white through the inverse mask.
        inv = ImageChops.invert(mask)
        white_through = Image.merge("RGB", (inv, inv, inv))
        return ImageChops.add(rgb, white_through)

    # Rare non-black matte: un-premultiply then paste.
    src = rgb.load()
    alpha_px = mask.load()
    straight = Image.new("RGB", rgb.size)
    dst = straight.load()
    width, height = rgb.size
    for y in range(height):
        for x in range(width):
            a = alpha_px[x, y] / 255.0
            r, g, b = (float(v) for v in src[x, y])
            if a <= 1e-6:
                dst[x, y] = (0, 0, 0)
                continue
            if a < 1.0:
                r = (r - matte_rgb[0] * (1.0 - a)) / a
                g = (g - matte_rgb[1] * (1.0 - a)) / a
                b = (b - matte_rgb[2] * (1.0 - a)) / a
            dst[x, y] = (
                int(round(max(0.0, min(255.0, r)))),
                int(round(max(0.0, min(255.0, g)))),
                int(round(max(0.0, min(255.0, b)))),
            )
    rgba = straight.convert("RGBA")
    rgba.putalpha(mask)
    bg = Image.new("RGB", rgb.size, (255, 255, 255))
    bg.paste(rgba, mask=mask)
    return bg


def extract_page_images(page: Any) -> list[dict[str, Any]]:
    """Decode page.images to PNG base64 with PDF-point bounding boxes.

    Soft masks (SMask) on stamps/signatures are applied and flattened onto white
    so Excel does not show a black rectangle behind the ink.
    """
    from PIL import Image

    images: list[dict[str, Any]] = []
    for image in page.images or []:
        stream = image.get("stream")
        if stream is None:
            continue
        try:
            raw = stream.get_data()
        except Exception:  # noqa: BLE001
            continue
        srcsize = image.get("srcsize") or (image.get("width"), image.get("height"))
        if not srcsize or len(srcsize) != 2:
            continue
        width_px, height_px = int(srcsize[0]), int(srcsize[1])
        if width_px <= 0 or height_px <= 0:
            continue
        try:
            pil = _decode_rgb_image(raw, width_px, height_px)
        except Exception:  # noqa: BLE001
            continue
        mask = _decode_soft_mask(stream, width_px, height_px)
        if mask is not None:
            attrs = getattr(stream, "attrs", None) or {}
            matte = attrs.get("Matte")
            if matte is not None:
                try:
                    matte = [float(x) for x in matte]
                except (TypeError, ValueError):
                    matte = None
            pil = _composite_smask_on_white(pil, mask, matte)
        elif pil.mode == "RGBA":
            bg = Image.new("RGB", pil.size, (255, 255, 255))
            bg.paste(pil, mask=pil.split()[3])
            pil = bg
        else:
            pil = pil.convert("RGB")
        buf = io.BytesIO()
        pil.save(buf, format="PNG")
        x0 = float(image.get("x0", 0))
        top = float(image.get("top", 0))
        x1 = float(image.get("x1", x0))
        bottom = float(image.get("bottom", top))
        images.append(
            {
                "x_pt": round(x0, 2),
                "y_pt": round(top, 2),
                "width_pt": round(x1 - x0, 2),
                "height_pt": round(bottom - top, 2),
                "mime": "image/png",
                "data_b64": base64.b64encode(buf.getvalue()).decode("ascii"),
            }
        )
    return images


def _char_covered(
    char: dict[str, Any],
    covered: list[tuple[float, float, float, float]],
) -> bool:
    mid_x = (char["x0"] + char["x1"]) / 2
    mid_y = (char["top"] + char["bottom"]) / 2
    for x0, top, x1, bottom in covered:
        if x0 - 0.5 <= mid_x < x1 + 0.5 and top - 0.5 <= mid_y < bottom + 0.5:
            return True
    return False


def loose_text_boxes(
    chars: list[dict[str, Any]],
    covered: list[tuple[float, float, float, float]],
) -> list[tuple[tuple[float, float, float, float], str, dict[str, Any] | None]]:
    """Turn free-floating chars (title, supplier/buyer) into grid boxes."""
    free = [char for char in chars if (char.get("text") or "").strip() and not _char_covered(char, covered)]
    if not free:
        return []
    ordered = sorted(free, key=lambda char: (round(char["top"], 1), char["x0"]))
    lines: list[list[dict[str, Any]]] = []
    current_top: float | None = None
    for char in ordered:
        if current_top is None or abs(char["top"] - current_top) > 1.6:
            lines.append([char])
            current_top = float(char["top"])
        else:
            lines[-1].append(char)

    boxes: list[tuple[tuple[float, float, float, float], str, dict[str, Any] | None]] = []
    for line in lines:
        line = sorted(line, key=lambda char: char["x0"])
        # Split a line into runs when a large horizontal gap appears (two labels).
        runs: list[list[dict[str, Any]]] = [[line[0]]]
        for char in line[1:]:
            prev = runs[-1][-1]
            gap = char["x0"] - prev["x1"]
            if gap > max(float(prev.get("size", 6)) * 1.8, 8.0):
                runs.append([char])
            else:
                runs[-1].append(char)
        for run in runs:
            text = text_from_chars(run)
            if not text:
                continue
            box = (
                float(min(c["x0"] for c in run)),
                float(min(c["top"] for c in run)),
                float(max(c["x1"] for c in run)),
                float(max(c["bottom"] for c in run)),
            )
            # Pad a little so the grid band matches visual line height.
            pad = max(0.5, float(run[0].get("size", 8)) * 0.15)
            padded = (box[0], box[1] - pad, box[2], box[3] + pad)
            boxes.append((padded, text, style_from_chars(run, padded)))
    return boxes


def sheet_from_page(page: Any, tables: list[Any]) -> dict[str, Any] | None:
    chars = list(page.chars or [])
    boxes: list[tuple[tuple[float, float, float, float], str, dict[str, Any] | None]] = []
    covered: list[tuple[float, float, float, float]] = []
    for table in tables:
        extracted = table.extract() or []
        for row_obj, row_text in zip(table.rows, extracted):
            for bbox, raw in zip(row_obj.cells, row_text):
                if bbox is None:
                    continue
                box = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
                covered.append(box)
                cell_chars = _chars_in_box(chars, box)
                if cell_chars:
                    text = text_from_chars(cell_chars)
                    style = style_from_chars(cell_chars, box)
                else:
                    text = "" if raw is None else str(raw).strip()
                    style = None
                if text:
                    boxes.append((box, text, style))
    boxes.extend(loose_text_boxes(chars, covered))
    images = extract_page_images(page)
    grid = build_grid(boxes)
    if not grid["rows"] and not images:
        return None
    if not grid["rows"]:
        # Image-only page: still emit a sheet so images can be placed.
        grid = {
            "rows": [[None]],
            "col_widths_pt": [float(page.width)],
            "row_heights_pt": [float(page.height)],
            "merges": [],
            "cell_styles": [[None]],
        }
    grid["images"] = images
    # Origin of the glued grid in page coordinates (top-left of first cell band).
    if boxes:
        grid["origin_x_pt"] = round(min(box[0] for box, _, _ in boxes), 2)
        grid["origin_y_pt"] = round(min(box[1] for box, _, _ in boxes), 2)
    else:
        grid["origin_x_pt"] = 0.0
        grid["origin_y_pt"] = 0.0
    return grid
