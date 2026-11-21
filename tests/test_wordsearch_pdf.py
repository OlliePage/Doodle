from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from colouring_factory.wordsearch_pdf import (
    create_wordsearch_pdf,
    grid_layout,
    preview_png,
)

DINO = (
    Path(__file__).resolve().parents[1] / "assets" / "demo_dinosaur.png"
).read_bytes()


@dataclass
class FakePlacement:
    display: str
    letters: str
    start: tuple[int, int]
    step: tuple[int, int]


@dataclass
class FakePuzzle:
    grid: tuple[str, ...]
    placements: list[FakePlacement]


def _puzzle() -> FakePuzzle:
    return FakePuzzle(
        grid=("CATXYZ", "QWDOGE", "RTYUIO", "FISHAS", "PLKJHG", "MNBVCX"),
        placements=[
            FakePlacement("Cat", "CAT", (0, 0), (0, 1)),
            FakePlacement("Dog", "DOG", (1, 2), (0, 1)),
            FakePlacement("Fish", "FISH", (3, 0), (0, 1)),
            FakePlacement("Cow", "CRP", (0, 0), (1, 0)),
            FakePlacement("Owl", "OIS", (1, 3), (1, 1)),
        ],
    )


def _clues(puzzle: FakePuzzle) -> dict[str, bytes | None]:
    return {p.display: DINO for p in puzzle.placements}


def test_two_pages_with_title_and_every_word() -> None:
    puzzle = _puzzle()
    pdf = create_wordsearch_pdf(
        puzzle, title="Farm friends", clues=_clues(puzzle), show_pictures=True
    )
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) == 2
    text = reader.pages[0].extract_text()
    assert "Farm friends" in text
    for placement in puzzle.placements:
        assert placement.display.upper() in text
    assert "Answers" in reader.pages[1].extract_text()


def test_renders_without_pictures() -> None:
    puzzle = _puzzle()
    all_none = create_wordsearch_pdf(
        puzzle,
        title="T",
        clues={p.display: None for p in puzzle.placements},
        show_pictures=True,
    )
    text_only = create_wordsearch_pdf(
        puzzle, title="T", clues=_clues(puzzle), show_pictures=False
    )
    for pdf in (all_none, text_only):
        assert len(PdfReader(BytesIO(pdf)).pages) == 2
        assert preview_png(pdf).startswith(b"\x89PNG")
    assert "OWL" in PdfReader(BytesIO(text_only)).pages[0].extract_text()


def test_preview_png_for_each_page() -> None:
    puzzle = _puzzle()
    pdf = create_wordsearch_pdf(
        puzzle, title="T", clues=_clues(puzzle), show_pictures=True
    )
    assert preview_png(pdf, page=1, zoom=1.0).startswith(b"\x89PNG")


def test_small_grid_letters_stay_large() -> None:
    # Reserve the height of two rows of picture clues, as the real page does.
    _, letter = grid_layout(6, 6, reserved_height=250)
    assert letter >= 24


def test_big_grid_still_fits_the_page() -> None:
    cell, _ = grid_layout(15, 15, reserved_height=250)
    assert cell * 15 <= 595.27 - 2 * 42
