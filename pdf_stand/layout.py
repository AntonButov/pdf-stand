from __future__ import annotations

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


def sheet_from_page(page: Any, tables: list[Any]) -> dict[str, Any] | None:
    chars = list(page.chars or [])
    boxes: list[tuple[tuple[float, float, float, float], str, dict[str, Any] | None]] = []
    for table in tables:
        extracted = table.extract() or []
        for row_obj, row_text in zip(table.rows, extracted):
            for bbox, raw in zip(row_obj.cells, row_text):
                if bbox is None:
                    continue
                box = (float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3]))
                cell_chars = _chars_in_box(chars, box)
                if cell_chars:
                    text = text_from_chars(cell_chars)
                    style = style_from_chars(cell_chars, box)
                else:
                    text = "" if raw is None else str(raw).strip()
                    style = None
                if text:
                    boxes.append((box, text, style))
    grid = build_grid(boxes)
    if not grid["rows"]:
        return None
    return grid
