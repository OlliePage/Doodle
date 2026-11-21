from __future__ import annotations

import math
from io import BytesIO
from typing import Protocol, Sequence

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .layouts import mm_to_pt
from .pdf_export import _draw_image_contain

MARGIN_PT = mm_to_pt(15)
MAX_CELL_PT = mm_to_pt(22)
CLUES_PER_ROW = 5
CLUE_GAP_PT = mm_to_pt(4)
CLUE_WORD_PT = mm_to_pt(8)
TITLE_BAND_PT = mm_to_pt(22)
LETTER_FRACTION = 0.6
FONT = "Helvetica-Bold"
RING_COLOURS = [
    colors.HexColor(code)
    for code in ("#e63946", "#2a9d8f", "#f4a261", "#457b9d", "#9b5de5", "#ef476f")
]


class PlacementLike(Protocol):
    display: str
    letters: str
    start: tuple[int, int]
    step: tuple[int, int]


class PuzzleLike(Protocol):
    grid: tuple[str, ...]
    placements: Sequence[PlacementLike]


def _clue_box_size() -> float:
    return (A4[0] - 2 * MARGIN_PT - (CLUES_PER_ROW - 1) * CLUE_GAP_PT) / CLUES_PER_ROW


def _clue_block_height(count: int, show_pictures: bool) -> float:
    if count == 0:
        return 0.0
    if not show_pictures:
        return math.ceil(count / 3) * mm_to_pt(10)
    rows = math.ceil(count / CLUES_PER_ROW)
    return rows * (_clue_box_size() + CLUE_WORD_PT + CLUE_GAP_PT)


def grid_layout(
    rows: int,
    cols: int,
    *,
    page_width: float = A4[0],
    page_height: float = A4[1],
    reserved_height: float = 0.0,
) -> tuple[float, float]:
    """Return (cell size, letter size) in points."""
    # The clue list sits below the grid, so the height budget shrinks with it;
    # the cap stops a 5x5 grid becoming a page of enormous squares.
    width_cap = (page_width - 2 * MARGIN_PT) / cols
    height_cap = (page_height - 2 * MARGIN_PT - TITLE_BAND_PT - reserved_height) / rows
    cell = min(width_cap, height_cap, MAX_CELL_PT)
    return cell, cell * LETTER_FRACTION


def _cells(placement: PlacementLike) -> list[tuple[int, int]]:
    r, c = placement.start
    dr, dc = placement.step
    return [(r + i * dr, c + i * dc) for i in range(len(placement.letters))]


def _draw_title(pdf: canvas.Canvas, text: str) -> None:
    width, height = A4
    size = 26.0
    while size > 12 and stringWidth(text, FONT, size) > width - 2 * MARGIN_PT:
        size -= 1
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT, size)
    pdf.drawCentredString(width / 2, height - MARGIN_PT - size, text)


def _draw_grid(
    pdf: canvas.Canvas, grid: Sequence[str], cell: float, top: float
) -> float:
    """Draw the grid with its top edge at `top`; return its left x."""
    rows, cols = len(grid), len(grid[0])
    left = (A4[0] - cols * cell) / 2
    pdf.setStrokeColor(colors.Color(0.75, 0.75, 0.75))
    pdf.setLineWidth(0.5)
    for r in range(rows + 1):
        pdf.line(left, top - r * cell, left + cols * cell, top - r * cell)
    for c in range(cols + 1):
        pdf.line(left + c * cell, top, left + c * cell, top - rows * cell)
    size = cell * LETTER_FRACTION
    pdf.setFillColor(colors.black)
    pdf.setFont(FONT, size)
    for r, row in enumerate(grid):
        for c, letter in enumerate(row):
            # Cap height is about 0.72 em, so dropping by 0.36 em centres the glyph.
            pdf.drawCentredString(
                left + (c + 0.5) * cell,
                top - (r + 0.5) * cell - size * 0.36,
                letter,
            )
    return left


def _draw_clues(
    pdf: canvas.Canvas,
    puzzle: PuzzleLike,
    clues: dict[str, bytes | None],
    show_pictures: bool,
    top: float,
) -> None:
    words = [p.display for p in puzzle.placements]
    # Printed in the grid's own case: a four-year-old matches the shapes of
    # letters, and "cat" under a grid of capitals is three shapes she has to
    # translate before she can look for them.
    capitals = any(letter.isupper() for letter in "".join(puzzle.grid))

    def shown(word: str) -> str:
        return word.upper() if capitals else word.lower()

    if not show_pictures:
        columns = 3
        per_column = math.ceil(len(words) / columns)
        col_width = (A4[0] - 2 * MARGIN_PT) / columns
        pdf.setFillColor(colors.black)
        pdf.setFont(FONT, 18)
        for i, word in enumerate(words):
            col, row = divmod(i, per_column)
            pdf.drawString(
                MARGIN_PT + col * col_width,
                top - (row + 1) * mm_to_pt(10) + mm_to_pt(3),
                shown(word),
            )
        return

    box = _clue_box_size()
    for i, word in enumerate(words):
        row, col = divmod(i, CLUES_PER_ROW)
        x = MARGIN_PT + col * (box + CLUE_GAP_PT)
        y_top = top - row * (box + CLUE_WORD_PT + CLUE_GAP_PT)
        pdf.setStrokeColor(colors.Color(0.7, 0.7, 0.7))
        pdf.setLineWidth(0.75)
        pdf.roundRect(x, y_top - box, box, box, 6, stroke=1, fill=0)
        image = clues.get(word)
        if image:
            pad = mm_to_pt(2)
            _draw_image_contain(
                pdf, image, x + pad, y_top - box + pad, box - 2 * pad, box - 2 * pad
            )
        size = 13.0
        while size > 7 and stringWidth(shown(word), FONT, size) > box:
            size -= 0.5
        pdf.setFillColor(colors.black)
        pdf.setFont(FONT, size)
        pdf.drawCentredString(
            x + box / 2, y_top - box - CLUE_WORD_PT + 3, shown(word)
        )


def _draw_ring(
    pdf: canvas.Canvas,
    placement: PlacementLike,
    left: float,
    top: float,
    cell: float,
    colour: colors.Color,
) -> None:
    cells = _cells(placement)

    def centre(rc: tuple[int, int]) -> tuple[float, float]:
        return left + (rc[1] + 0.5) * cell, top - (rc[0] + 0.5) * cell

    x0, y0 = centre(cells[0])
    x1, y1 = centre(cells[-1])
    length = math.hypot(x1 - x0, y1 - y0) + cell * 0.85
    thickness = cell * 0.85
    pdf.saveState()
    pdf.translate((x0 + x1) / 2, (y0 + y1) / 2)
    pdf.rotate(math.degrees(math.atan2(y1 - y0, x1 - x0)))
    pdf.setStrokeColor(colour)
    pdf.setFillColor(colour)
    pdf.setLineWidth(max(1.5, cell * 0.07))
    pdf.setFillAlpha(0.18)
    pdf.setStrokeAlpha(0.9)
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
    grid = puzzle.grid
    rows, cols = len(grid), len(grid[0])
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(title)

    reserved = _clue_block_height(len(puzzle.placements), show_pictures)
    cell, _ = grid_layout(rows, cols, reserved_height=reserved + mm_to_pt(8))
    grid_top = A4[1] - MARGIN_PT - TITLE_BAND_PT
    _draw_title(pdf, title)
    _draw_grid(pdf, grid, cell, grid_top)
    _draw_clues(pdf, puzzle, clues, show_pictures, grid_top - rows * cell - mm_to_pt(8))
    pdf.showPage()

    # The answer key uses a smaller grid so it reads as a key, not a second copy.
    answer_cell = min(cell, mm_to_pt(14))
    _draw_title(pdf, "Answers")
    left = _draw_grid(pdf, grid, answer_cell, grid_top)
    for i, placement in enumerate(puzzle.placements):
        _draw_ring(
            pdf,
            placement,
            left,
            grid_top,
            answer_cell,
            RING_COLOURS[i % len(RING_COLOURS)],
        )
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def preview_png(pdf_bytes: bytes, page: int = 0, zoom: float = 1.5) -> bytes:
    with pymupdf.open(stream=pdf_bytes, filetype="pdf") as document:
        pixmap = document[page].get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        return pixmap.tobytes("png")
