from __future__ import annotations

import math
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Protocol, Sequence

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .layouts import mm_to_pt
from .pdf_export import _draw_image_contain

FONT_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
# Andika was drawn for children learning to read: single-storey a and g, the
# shapes they are taught, and generous spacing. Sniglet is the rounded display
# face for titles, printed as an outline so the title is something to colour.
DISPLAY = "Sniglet-ExtraBold"
TEXT = "Andika"
TEXT_BOLD = "Andika-Bold"

FRAME_INSET = mm_to_pt(9)
FRAME_RADIUS = mm_to_pt(7)
CONTENT_PAD = mm_to_pt(9)
MAX_CELL_PT = mm_to_pt(24)
LETTER_FRACTION = 0.58
GRID_PAD = mm_to_pt(3)
SECTION_GAP = mm_to_pt(7)
MAX_PICTURE = mm_to_pt(40)
INK = colors.Color(0.08, 0.08, 0.1)
SOFT_INK = colors.Color(0.32, 0.33, 0.36)
HAIRLINE = colors.Color(0.8, 0.8, 0.82)

HEADER_H = mm_to_pt(9)
TITLE_MAX = 46.0
INSTRUCTION_H = mm_to_pt(8)
FOOTER_H = mm_to_pt(6)
PANEL_LABEL_H = mm_to_pt(9)
WORD_LINE_H = mm_to_pt(9)


class PlacementLike(Protocol):
    display: str
    letters: str
    start: tuple[int, int]
    step: tuple[int, int]


class PuzzleLike(Protocol):
    grid: tuple[str, ...]
    placements: Sequence[PlacementLike]


@lru_cache(maxsize=1)
def _register_fonts() -> None:
    for name, file in (
        (DISPLAY, "Sniglet-ExtraBold.ttf"),
        (TEXT, "Andika-Regular.ttf"),
        (TEXT_BOLD, "Andika-Bold.ttf"),
    ):
        pdfmetrics.registerFont(TTFont(name, str(FONT_DIR / file)))


def _content_box() -> tuple[float, float, float, float]:
    """Left, bottom, right, top of the area inside the frame's padding."""

    inset = FRAME_INSET + CONTENT_PAD
    return inset, inset, A4[0] - inset, A4[1] - inset


def grid_layout(
    rows: int,
    cols: int,
    *,
    page_width: float = A4[0],
    page_height: float = A4[1],
    reserved_height: float = 0.0,
) -> tuple[float, float]:
    """Return (cell size, letter size) in points."""

    inset = 2 * (FRAME_INSET + CONTENT_PAD + GRID_PAD)
    width_cap = (page_width - inset) / cols
    height_cap = (page_height - inset - reserved_height) / rows
    # The cap stops a 5x5 grid for a toddler becoming a page of huge squares
    # with nothing left over for the pictures she actually needs.
    cell = min(width_cap, height_cap, MAX_CELL_PT)
    return cell, cell * LETTER_FRACTION


def _cells(placement: PlacementLike) -> list[tuple[int, int]]:
    r, c = placement.start
    dr, dc = placement.step
    return [(r + i * dr, c + i * dc) for i in range(len(placement.letters))]


def _star(pdf: canvas.Canvas, cx: float, cy: float, radius: float) -> None:
    path = pdf.beginPath()
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.45
        angle = math.pi / 2 + i * math.pi / 5
        x, y = cx + r * math.cos(angle), cy + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.close()
    pdf.drawPath(path, stroke=1, fill=1)


def _draw_frame(pdf: canvas.Canvas) -> None:
    width, height = A4
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(2.4)
    pdf.roundRect(
        FRAME_INSET,
        FRAME_INSET,
        width - 2 * FRAME_INSET,
        height - 2 * FRAME_INSET,
        FRAME_RADIUS,
    )
    gap = mm_to_pt(2.2)
    pdf.setLineWidth(0.7)
    pdf.roundRect(
        FRAME_INSET + gap,
        FRAME_INSET + gap,
        width - 2 * (FRAME_INSET + gap),
        height - 2 * (FRAME_INSET + gap),
        FRAME_RADIUS - gap,
    )
    # Outline stars over the corners: the cheapest decoration that makes the
    # page look finished, and four more things for a child to colour.
    pdf.setFillColor(colors.white)
    pdf.setLineWidth(1.4)
    pdf.setLineJoin(1)
    offset = FRAME_INSET + mm_to_pt(2.5)
    for cx, cy in (
        (offset, offset),
        (width - offset, offset),
        (offset, height - offset),
        (width - offset, height - offset),
    ):
        _star(pdf, cx, cy, mm_to_pt(6.5))


def _fit(text: str, font: str, size: float, width: float, floor: float) -> float:
    while size > floor and stringWidth(text, font, size) > width:
        size -= 0.5
    return size


def _draw_header(pdf: canvas.Canvas, top: float) -> None:
    left, _bottom, right, _top = _content_box()
    baseline = top - mm_to_pt(5)
    pdf.setFillColor(SOFT_INK)
    pdf.setStrokeColor(SOFT_INK)
    pdf.setLineWidth(0.8)
    pdf.setFont(TEXT, 11)
    pdf.drawString(left, baseline, "Name")
    name_start = left + stringWidth("Name", TEXT, 11) + mm_to_pt(2)
    date_label_x = right - mm_to_pt(48)
    pdf.line(name_start, baseline - 2, date_label_x - mm_to_pt(8), baseline - 2)
    pdf.drawString(date_label_x, baseline, "Date")
    date_start = date_label_x + stringWidth("Date", TEXT, 11) + mm_to_pt(2)
    pdf.line(date_start, baseline - 2, right, baseline - 2)


def _draw_title(pdf: canvas.Canvas, text: str, top: float, *, outline: bool) -> float:
    """Draw the title below `top` and return its height."""

    left, _bottom, right, _top = _content_box()
    size = _fit(text, DISPLAY, TITLE_MAX, right - left, 20)
    baseline = top - size * 0.95
    pdf.saveState()
    pdf.setFillColor(INK)
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.5)
    pdf.setLineJoin(1)
    text_object = pdf.beginText()
    text_object.setFont(DISPLAY, size)
    # Render mode 1 strokes the letter outlines without filling them, which
    # turns the title into bubble letters a child can colour in.
    text_object.setTextRenderMode(1 if outline else 0)
    text_object.setTextOrigin((A4[0] - stringWidth(text, DISPLAY, size)) / 2, baseline)
    text_object.textOut(text)
    pdf.drawText(text_object)
    pdf.restoreState()
    return size * 1.25


def _draw_instruction(pdf: canvas.Canvas, text: str, top: float) -> None:
    pdf.setFillColor(SOFT_INK)
    pdf.setFont(TEXT, 13)
    pdf.drawCentredString(A4[0] / 2, top - mm_to_pt(5.5), text)


def _draw_grid(
    pdf: canvas.Canvas, grid: Sequence[str], cell: float, top: float
) -> float:
    """Draw the framed grid with its frame's top edge at `top`; return the
    left x of the first cell."""

    rows, cols = len(grid), len(grid[0])
    left = (A4[0] - cols * cell) / 2
    cells_top = top - GRID_PAD
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(2.2)
    pdf.roundRect(
        left - GRID_PAD,
        cells_top - rows * cell - GRID_PAD,
        cols * cell + 2 * GRID_PAD,
        rows * cell + 2 * GRID_PAD,
        mm_to_pt(4),
    )
    # Faint lines keep a young child's eye on one row without the page reading
    # as a spreadsheet.
    pdf.setStrokeColor(HAIRLINE)
    pdf.setLineWidth(0.6)
    for r in range(1, rows):
        y = cells_top - r * cell
        pdf.line(left, y, left + cols * cell, y)
    for c in range(1, cols):
        x = left + c * cell
        pdf.line(x, cells_top, x, cells_top - rows * cell)
    size = cell * LETTER_FRACTION
    ascent = pdfmetrics.getFont(TEXT_BOLD).face.ascent / 1000
    pdf.setFillColor(INK)
    pdf.setFont(TEXT_BOLD, size)
    for r, row in enumerate(grid):
        for c, letter in enumerate(row):
            # Andika's capitals stand about 0.66 of its ascent; half of that
            # below the centre line sits the glyph in the middle of its square.
            pdf.drawCentredString(
                left + (c + 0.5) * cell,
                cells_top - (r + 0.5) * cell - size * ascent * 0.33,
                letter,
            )
    return left


def _bank_layout(
    count: int, width: float, show_pictures: bool
) -> tuple[int, int, float]:
    """Items per row, rows, and picture size for the words-to-find panel."""

    if count == 0:
        return 0, 0, 0.0
    if not show_pictures:
        per_row = min(count, 3)
        return per_row, math.ceil(count / per_row), 0.0
    per_row = count if count <= 5 else math.ceil(count / 2)
    per_row = min(per_row, 6)
    rows = math.ceil(count / per_row)
    picture = min(width / per_row * 0.74, MAX_PICTURE)
    return per_row, rows, picture


def _bank_height(rows: int, picture: float, show_pictures: bool) -> float:
    if rows == 0:
        return 0.0
    row_h = (
        (picture + WORD_LINE_H + mm_to_pt(4))
        if show_pictures
        else WORD_LINE_H + mm_to_pt(2)
    )
    return PANEL_LABEL_H + rows * row_h + mm_to_pt(5)


def _checkbox(pdf: canvas.Canvas, x: float, baseline: float, size: float) -> None:
    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.1)
    pdf.roundRect(x, baseline - size * 0.12, size, size, size * 0.22, stroke=1, fill=0)


def _draw_word_bank(
    pdf: canvas.Canvas,
    words: list[str],
    clues: dict[str, bytes | None],
    shown,
    show_pictures: bool,
    top: float,
    height: float,
    picture_override: float | None = None,
) -> None:
    left, _bottom, right, _top = _content_box()
    inner_left, inner_right = left + mm_to_pt(5), right - mm_to_pt(5)
    per_row, rows, picture = _bank_layout(
        len(words), inner_right - inner_left, show_pictures
    )
    if picture_override:
        picture = picture_override

    pdf.setStrokeColor(INK)
    pdf.setLineWidth(1.6)
    pdf.roundRect(left, top - height, right - left, height, mm_to_pt(5))

    label = "Words to find"
    label_size = 17.0
    label_w = stringWidth(label, DISPLAY, label_size) + mm_to_pt(10)
    label_h = mm_to_pt(8.5)
    pdf.setFillColor(colors.white)
    pdf.roundRect(
        (A4[0] - label_w) / 2,
        top - label_h / 2,
        label_w,
        label_h,
        label_h / 2,
        stroke=1,
        fill=1,
    )
    pdf.setFillColor(INK)
    pdf.setFont(DISPLAY, label_size)
    pdf.drawCentredString(A4[0] / 2, top - label_size * 0.32, label)

    item_w = (inner_right - inner_left) / per_row
    row_h = (
        (picture + WORD_LINE_H + mm_to_pt(4))
        if show_pictures
        else WORD_LINE_H + mm_to_pt(2)
    )
    used_h = rows * row_h
    first_top = (
        top - PANEL_LABEL_H - (height - PANEL_LABEL_H - used_h) / 2 + mm_to_pt(1)
    )

    for index, word in enumerate(words):
        row, col = divmod(index, per_row)
        # The last row is centred rather than left-aligned, so seven words read
        # as four and three rather than four and a gap.
        in_row = min(per_row, len(words) - row * per_row)
        row_left = inner_left + (per_row - in_row) * item_w / 2
        cx = row_left + (col + 0.5) * item_w
        y_top = first_top - row * row_h
        text = shown(word)
        if show_pictures:
            image = clues.get(word)
            if image:
                _draw_image_contain(
                    pdf, image, cx - picture / 2, y_top - picture, picture, picture
                )
            baseline = y_top - picture - mm_to_pt(6.5)
        else:
            baseline = y_top - mm_to_pt(7)
        size = _fit(
            text, TEXT_BOLD, 18 if not show_pictures else 16, item_w - mm_to_pt(9), 9
        )
        box = size * 0.72
        text_w = stringWidth(text, TEXT_BOLD, size)
        start = cx - (text_w + box + mm_to_pt(2)) / 2
        _checkbox(pdf, start, baseline, box)
        pdf.setFillColor(INK)
        pdf.setFont(TEXT_BOLD, size)
        pdf.drawString(start + box + mm_to_pt(2), baseline, text)


def _draw_footer(pdf: canvas.Canvas, text: str) -> None:
    _left, bottom, _right, _top = _content_box()
    pdf.setFillColor(SOFT_INK)
    pdf.setFont(TEXT, 9)
    pdf.drawCentredString(A4[0] / 2, bottom - mm_to_pt(1), text)


def _draw_ring(
    pdf: canvas.Canvas,
    placement: PlacementLike,
    left: float,
    cells_top: float,
    cell: float,
) -> None:
    cells = _cells(placement)

    def centre(rc: tuple[int, int]) -> tuple[float, float]:
        return left + (rc[1] + 0.5) * cell, cells_top - (rc[0] + 0.5) * cell

    x0, y0 = centre(cells[0])
    x1, y1 = centre(cells[-1])
    thickness = cell * 0.78
    length = math.hypot(x1 - x0, y1 - y0) + thickness
    pdf.saveState()
    pdf.translate((x0 + x1) / 2, (y0 + y1) / 2)
    pdf.rotate(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    # Grey and black only: the key is for the grown-up and prints the same on
    # a black-and-white printer as on screen.
    pdf.setStrokeColor(INK)
    pdf.setFillColor(colors.Color(0, 0, 0))
    pdf.setLineWidth(max(1.2, cell * 0.05))
    pdf.setFillAlpha(0.1)
    pdf.roundRect(
        -length / 2, -thickness / 2, length, thickness, thickness / 2, stroke=1, fill=1
    )
    pdf.restoreState()


def create_wordsearch_pdf(
    puzzle: PuzzleLike,
    *,
    title: str,
    clues: dict[str, bytes | None],
    show_pictures: bool,
) -> bytes:
    _register_fonts()
    grid = puzzle.grid
    rows, cols = len(grid), len(grid[0])
    words = [p.display for p in puzzle.placements]
    # Printed in the grid's own case: a four-year-old matches the shapes of
    # letters, and "cat" under a grid of capitals is three shapes she has to
    # translate before she can look for them.
    capitals = any(letter.isupper() for letter in "".join(grid))

    def shown(word: str) -> str:
        return word.upper() if capitals else word.lower()

    left, bottom, right, top = _content_box()
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(title)

    # Page 1: every block is measured first, then the spare height is shared
    # out as equal gaps, so a small grid sits in a balanced page rather than
    # at the top of an empty one.
    _draw_frame(pdf)
    _draw_header(pdf, top)
    title_size = _fit(title, DISPLAY, TITLE_MAX, right - left, 20)
    title_h = title_size * 1.25
    per_row, bank_rows, picture = _bank_layout(
        len(words), right - left - mm_to_pt(10), show_pictures
    )
    available = (top - HEADER_H) - (bottom + FOOTER_H) - title_h - INSTRUCTION_H
    bank_h = _bank_height(bank_rows, picture, show_pictures)
    cell, _letter = grid_layout(
        rows,
        cols,
        reserved_height=bank_h
        + 3 * SECTION_GAP
        + HEADER_H
        + title_h
        + INSTRUCTION_H
        + FOOTER_H,
    )
    grid_h = rows * cell + 2 * GRID_PAD
    spare = available - grid_h - bank_h - 2 * SECTION_GAP
    # Spare room goes first into bigger pictures, which is what a child who
    # cannot read the words relies on, then into the gaps.
    if show_pictures and bank_rows and spare > 0:
        grown = min(MAX_PICTURE * 1.25, picture + spare * 0.5 / bank_rows)
        grown = min(grown, (right - left - mm_to_pt(10)) / per_row * 0.8)
        bank_h += (grown - picture) * bank_rows
        spare -= (grown - picture) * bank_rows
        picture = grown
    gap = SECTION_GAP + max(0.0, spare) / 3

    cursor = top - HEADER_H - max(0.0, spare) / 6
    _draw_title(pdf, title, cursor, outline=True)
    cursor -= title_h
    _draw_instruction(
        pdf, "Find each word, tick it off, then colour the pictures!", cursor
    )
    cursor -= INSTRUCTION_H + gap
    _draw_grid(pdf, grid, cell, cursor)
    cursor -= grid_h + gap
    if words:
        _draw_word_bank(
            pdf,
            words,
            clues,
            shown,
            show_pictures,
            cursor,
            bank_h,
            picture_override=picture if show_pictures else None,
        )
    _draw_footer(pdf, "Answers are on the next page")
    pdf.showPage()

    # Page 2: the key, for the grown-up. Smaller, so it reads as a key rather
    # than a second copy to hand out.
    _draw_frame(pdf)
    title_h = _draw_title(pdf, "Answers", top - mm_to_pt(2), outline=False)
    answer_cell = min(cell, mm_to_pt(15))
    grid_top = top - mm_to_pt(2) - title_h - SECTION_GAP
    grid_left = _draw_grid(pdf, grid, answer_cell, grid_top)
    for placement in puzzle.placements:
        _draw_ring(pdf, placement, grid_left, grid_top - GRID_PAD, answer_cell)
    list_top = grid_top - rows * answer_cell - 2 * GRID_PAD - SECTION_GAP
    pdf.setFillColor(INK)
    pdf.setFont(TEXT_BOLD, 13)
    pdf.drawCentredString(
        A4[0] / 2, list_top - mm_to_pt(4), "   ·   ".join(shown(w) for w in words)
    )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def preview_png(pdf_bytes: bytes, page: int = 0, zoom: float = 1.5) -> bytes:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        pixmap = document[page].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pixmap.tobytes("png")
