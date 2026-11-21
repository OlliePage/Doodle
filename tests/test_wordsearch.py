from colouring_factory.storage import QUICK_AGE_CHOICES
from colouring_factory.wordsearch import (
    PRESETS,
    WordSearchSettings,
    build_puzzle,
    parse_word_input,
)

WORDS = [(w.title(), w) for w in ("CAT", "DOG", "BIRD", "FISH", "HORSE", "MOUSE")]


def test_every_placement_reads_back_from_the_grid():
    puzzle = build_puzzle(WORDS, PRESETS["Grown-up"], seed=3)
    assert puzzle.placements
    for p in puzzle.placements:
        assert "".join(puzzle.grid[r][c] for r, c in p.cells()) == p.letters


def test_only_allowed_directions_are_used():
    for seed in range(20):
        puzzle = build_puzzle(WORDS, PRESETS["4-5 years"], seed)
        for p in puzzle.placements:
            assert p.step in {(0, 1), (1, 0)}


def test_backwards_reverses_every_allowed_step():
    settings = WordSearchSettings(8, 8, 5, 3, 6, frozenset({"across", "backwards"}))
    steps = {
        p.step
        for seed in range(30)
        for p in build_puzzle(WORDS, settings, seed).placements
    }
    assert steps == {(0, 1), (0, -1)}


def test_same_seed_gives_same_grid_and_other_seed_differs():
    settings = PRESETS["6-9 years"]
    assert build_puzzle(WORDS, settings, 7) == build_puzzle(WORDS, settings, 7)
    assert (
        build_puzzle(WORDS, settings, 7).grid != build_puzzle(WORDS, settings, 8).grid
    )


def test_word_too_long_for_the_grid_is_skipped_with_a_reason():
    words = [("Elephantine", "ELEPHANTINE"), ("Cat", "CAT")]
    puzzle = build_puzzle(words, PRESETS["2-3 years"], 1)
    assert [s.word for s in puzzle.skipped] == ["Elephantine"]
    assert puzzle.skipped[0].reason
    assert puzzle.placed == ("Cat",)


def test_lowercase_setting_lowercases_the_grid():
    settings = WordSearchSettings(6, 6, 3, 3, 5, frozenset({"across"}), uppercase=False)
    puzzle = build_puzzle(WORDS[:3], settings, 2)
    assert all(row == row.lower() for row in puzzle.grid)
    for p in puzzle.placements:
        assert "".join(puzzle.grid[r][c] for r, c in p.cells()) == p.letters.lower()


def test_presets_cover_every_age_choice():
    assert set(PRESETS) == set(QUICK_AGE_CHOICES)


def test_settings_round_trip_and_clamp():
    s = PRESETS["Grown-up"]
    assert WordSearchSettings.from_dict(s.to_dict()) == s
    clamped = WordSearchSettings.from_dict(
        {"rows": 99, "cols": 1, "word_count": 0, "directions": ["bogus"]}
    )
    assert (clamped.rows, clamped.cols, clamped.word_count) == (15, 5, 3)
    assert clamped.directions == frozenset({"across"})


def test_commas_and_new_lines_give_words():
    for text in ("cat, dog,bird", "cat\ndog\nbird"):
        parsed = parse_word_input(text)
        assert parsed.kind == "words"
        assert [d for d, _ in parsed.words] == ["cat", "dog", "bird"]


def test_single_phrase_is_a_topic():
    parsed = parse_word_input("sea creatures")
    assert parsed.kind == "topic"
    assert parsed.topic == "sea creatures"


def test_punctuation_dropped_blanks_and_duplicates_removed():
    parsed = parse_word_input("Ice cream!, , ICE-CREAM, it's,")
    assert parsed.words == (("Ice cream!", "ICECREAM"), ("it's", "ITS"))


def test_a_full_fit_seed_places_every_word() -> None:
    from colouring_factory.wordsearch import seed_that_fits

    words = [("cat", "CAT"), ("dog", "DOG"), ("hen", "HEN"), ("owl", "OWL")]
    settings = PRESETS["2-3 years"]
    seed = seed_that_fits(words, settings, 1)

    assert seed is not None
    assert build_puzzle(words, settings, seed).skipped == ()


def test_the_smallest_grid_is_reported_for_a_list_that_overflows() -> None:
    from colouring_factory.wordsearch import smallest_grid_that_fits

    words = [(w, w.upper()) for w in ("elephant", "cat", "dog")]
    # Eight letters cannot go in a 5 x 5 grid in any direction.
    assert smallest_grid_that_fits(words, PRESETS["2-3 years"]) == 8


def _shared_cells(puzzle) -> int:
    from collections import Counter

    uses = Counter(cell for p in puzzle.placements for cell in p.cells())
    return sum(1 for n in uses.values() if n > 1)


def test_words_cross_and_borrow_letters_from_each_other() -> None:
    # Ollie: every word sat in its own row or column, so the sheet was dull
    # and wasted space. Christmas words share plenty of letters; across 20
    # sheets they should cross on every one.
    words = [
        (w, w.upper())
        for w in ("sleigh", "santa", "bells", "angel", "tree", "star", "gift", "snow")
    ]
    for seed in range(1, 21):
        puzzle = build_puzzle(words, PRESETS["6-9 years"], seed)
        assert puzzle.skipped == ()
        assert _shared_cells(puzzle) >= 3, seed


def test_a_word_is_never_hidden_inside_another() -> None:
    # CAT lying wholly inside CATERPILLAR could never be circled on its own.
    words = [("caterpillar", "CATERPILLAR"), ("cat", "CAT"), ("pill", "PILL")]
    for seed in range(1, 21):
        puzzle = build_puzzle(words, PRESETS["Grown-up"], seed)
        cells = {p.word: set(p.cells()) for p in puzzle.placements}
        assert not cells["cat"] <= cells["caterpillar"]
        assert not cells["pill"] <= cells["caterpillar"]
