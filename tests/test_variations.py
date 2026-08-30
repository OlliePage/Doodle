import pytest

from colouring_factory.variations import VARIATION_AXES, axis_briefs


def test_axis_briefs_returns_the_requested_count() -> None:
    for count in (1, 2, 3, 4):
        assert len(axis_briefs("a bear flying a kite", count)) == count


def test_axis_briefs_are_all_different() -> None:
    briefs = axis_briefs("a bear flying a kite", 4)
    assert len(set(briefs)) == 4


def test_every_brief_mentions_the_concept() -> None:
    for brief in axis_briefs("a bear flying a kite", 4):
        assert "a bear flying a kite" in brief


def test_axis_briefs_are_deterministic_for_the_same_request() -> None:
    assert axis_briefs("a bear flying a kite", 3) == axis_briefs(
        "a bear flying a kite", 3
    )


def test_different_concepts_get_different_briefs() -> None:
    bear = axis_briefs("a bear flying a kite", 3)
    dino = axis_briefs("a dinosaur washing a fire engine", 3)
    assert bear != dino


def test_a_shorter_request_is_a_prefix_of_a_longer_one() -> None:
    # Asking for one more alternative should add to the set, not reshuffle it,
    # so that pressing "another" keeps the pictures the user has already seen.
    assert (
        axis_briefs("a bear flying a kite", 2)
        == axis_briefs("a bear flying a kite", 4)[:2]
    )


def test_each_brief_varies_all_four_axes() -> None:
    briefs = axis_briefs("a bear flying a kite", 4)
    for axis_values in VARIATION_AXES.values():
        used = [
            value for value in axis_values if any(value in brief for brief in briefs)
        ]
        assert len(used) >= 2, (
            "at least two distinct values per axis across four briefs"
        )


def test_an_empty_concept_is_refused() -> None:
    with pytest.raises(ValueError):
        axis_briefs("   ", 2)


def test_a_count_outside_one_to_four_is_refused() -> None:
    with pytest.raises(ValueError):
        axis_briefs("a bear", 0)
    with pytest.raises(ValueError):
        axis_briefs("a bear", 5)
