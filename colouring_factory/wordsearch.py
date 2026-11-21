from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass, replace
from typing import Any, Literal

ALL_DIRECTIONS: frozenset[str] = frozenset({"across", "down", "diagonal", "backwards"})

_FORWARD_STEPS: dict[str, tuple[tuple[int, int], ...]] = {
    "across": ((0, 1),),
    "down": ((1, 0),),
    "diagonal": ((1, 1), (-1, 1)),
}


@dataclass(frozen=True)
class WordSearchSettings:
    rows: int
    cols: int
    word_count: int
    min_len: int
    max_len: int
    directions: frozenset[str]
    uppercase: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rows": self.rows,
            "cols": self.cols,
            "word_count": self.word_count,
            "min_len": self.min_len,
            "max_len": self.max_len,
            "directions": sorted(self.directions),
            "uppercase": self.uppercase,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WordSearchSettings:
        # Favourites come from a hand-editable settings file, so clamp to the
        # ranges the controls offer instead of trusting whatever is stored.
        def clamp(value: Any, low: int, high: int) -> int:
            return max(low, min(high, int(value)))

        directions = (
            frozenset(str(d) for d in data.get("directions", ())) & ALL_DIRECTIONS
        )
        return cls(
            rows=clamp(data["rows"], 5, 15),
            cols=clamp(data["cols"], 5, 15),
            word_count=clamp(data["word_count"], 3, 15),
            min_len=clamp(data.get("min_len", 3), 2, 15),
            max_len=clamp(data.get("max_len", 8), 2, 15),
            directions=directions or frozenset({"across"}),
            uppercase=bool(data.get("uppercase", True)),
        )


PRESETS: dict[str, WordSearchSettings] = {
    "2-3 years": WordSearchSettings(5, 5, 3, 3, 4, frozenset({"across"})),
    "4-5 years": WordSearchSettings(6, 6, 5, 3, 5, frozenset({"across", "down"})),
    "6-9 years": WordSearchSettings(
        10, 10, 8, 3, 8, frozenset({"across", "down", "diagonal"})
    ),
    "Grown-up": WordSearchSettings(14, 14, 14, 4, 12, ALL_DIRECTIONS),
}


@dataclass(frozen=True)
class WordInput:
    kind: Literal["words", "topic"]
    words: tuple[tuple[str, str], ...] = ()
    topic: str = ""


def parse_word_input(text: str) -> WordInput:
    if "," not in text and "\n" not in text:
        return WordInput(kind="topic", topic=text.strip())
    seen: set[str] = set()
    words: list[tuple[str, str]] = []
    for part in re.split(r"[,\n]", text):
        display = " ".join(part.split())
        letters = re.sub(r"[^A-Z]", "", display.upper())
        if not letters or letters in seen:
            continue
        seen.add(letters)
        words.append((display, letters))
    return WordInput(kind="words", words=tuple(words))


@dataclass(frozen=True)
class Placement:
    word: str
    letters: str
    start: tuple[int, int]
    step: tuple[int, int]

    # The PDF module reads the word as it should be printed under its picture
    # through this name, so it never has to import this module.
    @property
    def display(self) -> str:
        return self.word

    def cells(self) -> list[tuple[int, int]]:
        row, col = self.start
        dr, dc = self.step
        return [(row + dr * i, col + dc * i) for i in range(len(self.letters))]


@dataclass(frozen=True)
class Skipped:
    word: str
    reason: str


@dataclass(frozen=True)
class Puzzle:
    grid: tuple[str, ...]
    placements: tuple[Placement, ...]
    placed: tuple[str, ...]
    skipped: tuple[Skipped, ...]


def _steps_for(directions: frozenset[str]) -> list[tuple[int, int]]:
    steps: list[tuple[int, int]] = []
    for name in ("across", "down", "diagonal"):
        if name in directions:
            steps.extend(_FORWARD_STEPS[name])
    if "backwards" in directions:
        # Backwards alone has no forward step to reverse, so read across leftwards.
        steps.extend([(-dr, -dc) for dr, dc in steps] or [(0, -1)])
    return steps or [(0, 1)]


def _fits(
    cells: list[list[str]], letters: str, start: tuple[int, int], step: tuple[int, int]
) -> bool:
    rows, cols = len(cells), len(cells[0])
    r, c = start
    end_r = r + step[0] * (len(letters) - 1)
    end_c = c + step[1] * (len(letters) - 1)
    if not (0 <= end_r < rows and 0 <= end_c < cols):
        return False
    for i, ch in enumerate(letters):
        here = cells[r + step[0] * i][c + step[1] * i]
        if here and here != ch:
            return False
    return True


_LAYOUTS_PER_PUZZLE = 6


def _shared_letters(
    cells: list[list[str]], letters: str, start: tuple[int, int], step: tuple[int, int]
) -> int:
    r, c = start
    return sum(
        1 for i in range(len(letters)) if cells[r + step[0] * i][c + step[1] * i]
    )


def _lay_out(
    words: list[tuple[str, str]],
    rows: int,
    cols: int,
    steps: list[tuple[int, int]],
    rng: random.Random,
) -> tuple[list[list[str]], list[Placement], list[Skipped], int]:
    """One attempt at the whole grid, crossing words wherever it can.

    Like a crossword compiler: every spot and direction a word could go is
    considered, and it goes where it borrows the most letters from words
    already down. Among equally good spots one is picked at random, so each
    sheet still differs.
    """

    cells: list[list[str]] = [["" for _ in range(cols)] for _ in range(rows)]
    placements: list[Placement] = []
    skipped: list[Skipped] = []
    crossings = 0

    # Longest first: long words give the short ones the most letters to
    # borrow, and short words fit into the gaps that long ones leave.
    for display, letters in sorted(words, key=lambda w: -len(w[1])):
        if len(letters) > max(rows, cols):
            skipped.append(Skipped(display, "too long for the grid"))
            continue
        best = -1
        choices: list[tuple[tuple[int, int], tuple[int, int]]] = []
        for step in steps:
            for r in range(rows):
                for c in range(cols):
                    if not _fits(cells, letters, (r, c), step):
                        continue
                    shared = _shared_letters(cells, letters, (r, c), step)
                    # A word lying wholly inside another could never be
                    # circled on its own: CAT vanishing into CATERPILLAR.
                    if shared == len(letters):
                        continue
                    if shared > best:
                        best, choices = shared, [((r, c), step)]
                    elif shared == best:
                        choices.append(((r, c), step))
        if not choices:
            skipped.append(Skipped(display, "no room left in the grid"))
            continue
        start, step = rng.choice(choices)
        placement = Placement(display, letters, start, step)
        for (r, c), ch in zip(placement.cells(), letters, strict=True):
            cells[r][c] = ch
        placements.append(placement)
        crossings += best
    return cells, placements, skipped, crossings


def build_puzzle(
    words: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    settings: WordSearchSettings,
    seed: int,
) -> Puzzle:
    rng = random.Random(seed)
    rows, cols = settings.rows, settings.cols
    steps = _steps_for(settings.directions)

    # Several whole layouts, keeping the one that places the most words and,
    # among those, shares the most letters. The first word's spot decides
    # what every later word can borrow, so one try is often a poor one.
    best_layout = None
    best_score = (-1, -1)
    for _ in range(_LAYOUTS_PER_PUZZLE):
        layout = _lay_out(list(words), rows, cols, steps, rng)
        score = (len(layout[1]), layout[3])
        if score > best_score:
            best_layout, best_score = layout, score
    assert best_layout is not None
    cells, placements, skipped, _crossings = best_layout

    for r in range(rows):
        for c in range(cols):
            if not cells[r][c]:
                cells[r][c] = rng.choice(string.ascii_uppercase)

    grid = tuple("".join(row) for row in cells)
    if not settings.uppercase:
        grid = tuple(row.lower() for row in grid)
    return Puzzle(
        grid=grid,
        placements=tuple(placements),
        placed=tuple(p.word for p in placements),
        skipped=tuple(skipped),
    )


def seed_that_fits(
    words: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    settings: WordSearchSettings,
    seed: int,
    tries: int = 40,
) -> int | None:
    """A seed whose grid holds every word, or None if none was found.

    Placement is random, so a tight grid that one seed cannot fill another
    often can; trying a few before giving up is what lets a parent's own
    list fill a small grid rather than lose a word to bad luck.
    """

    # A list that plainly cannot fit is refused at once rather than after
    # forty full attempts, which for a hundred words would be seconds.
    longest = max((len(letters) for _display, letters in words), default=0)
    total = sum(len(letters) for _display, letters in words)
    if longest > max(settings.rows, settings.cols) or total > (
        settings.rows * settings.cols * 1.3
    ):
        return None
    rng = random.Random(seed)
    for _ in range(tries):
        candidate = rng.randrange(1, 2**31)
        if not build_puzzle(words, settings, candidate).skipped:
            return candidate
    return None


def smallest_grid_that_fits(
    words: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    settings: WordSearchSettings,
    largest: int = 15,
) -> int | None:
    """The smallest square grid, larger than the current one, that holds
    every word, or None when even the largest cannot."""

    longest = max((len(letters) for _display, letters in words), default=0)
    total = sum(len(letters) for _display, letters in words)
    for size in range(max(settings.rows, settings.cols) + 1, largest + 1):
        # Cheap refusals first: a word longer than a side cannot be placed in
        # any direction, and overlaps rarely save more than a third of the
        # letters, so a grid that small is not worth searching.
        if longest > size or total > size * size * 1.3:
            continue
        trial = replace(settings, rows=size, cols=size)
        if seed_that_fits(words, trial, size, tries=12) is not None:
            return size
    return None
