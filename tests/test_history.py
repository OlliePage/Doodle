import pytest

from colouring_factory.history import ancestry, append, start
from colouring_factory.models import GeneratedArtwork


def _art(tag: str) -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=tag.encode(), prompt=tag, provider="Test", model="test"
    )


def test_a_chain_starts_with_one_unattributed_version() -> None:
    chain = start(_art("original"))
    assert len(chain) == 1
    assert chain[0].instruction == ""
    assert chain[0].parent is None


def test_appending_records_the_instruction_and_the_parent() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hatted"), "add a hat", parent=0)
    assert len(chain) == 2
    assert chain[1].instruction == "add a hat"
    assert chain[1].parent == 0


def test_the_chain_is_append_only() -> None:
    # Backing out of a direction must never destroy what came after, so a
    # refinement from an earlier version adds rather than truncates.
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    chain = append(chain, _art("scarf"), "add a scarf", parent=1)
    chain = append(chain, _art("boots"), "add boots", parent=0)

    assert len(chain) == 4
    assert [v.parent for v in chain] == [None, 0, 1, 0]
    assert chain[2].instruction == "add a scarf"


def test_versions_are_immutable() -> None:
    chain = start(_art("original"))
    with pytest.raises(Exception):
        chain[0].instruction = "changed"


def test_appending_returns_a_new_chain() -> None:
    first = start(_art("original"))
    second = append(first, _art("hat"), "add a hat", parent=0)
    assert len(first) == 1
    assert first is not second


def test_ancestry_walks_back_to_the_original() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    chain = append(chain, _art("scarf"), "add a scarf", parent=1)
    assert ancestry(chain, 2) == (0, 1, 2)
    assert ancestry(chain, 0) == (0,)


def test_ancestry_of_a_sibling_branch_skips_the_other_branch() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    chain = append(chain, _art("boots"), "add boots", parent=0)
    assert ancestry(chain, 2) == (0, 2)


def test_an_unknown_parent_is_refused() -> None:
    chain = start(_art("original"))
    with pytest.raises(ValueError):
        append(chain, _art("hat"), "add a hat", parent=7)


def test_a_negative_parent_is_refused() -> None:
    chain = start(_art("original"))
    with pytest.raises(ValueError):
        append(chain, _art("hat"), "add a hat", parent=-1)


def test_an_empty_instruction_is_refused() -> None:
    chain = start(_art("original"))
    with pytest.raises(ValueError):
        append(chain, _art("hat"), "   ", parent=0)


def test_starting_again_abandons_the_previous_chain() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    fresh = start(_art("different"))
    assert len(fresh) == 1
    assert fresh[0].artwork.prompt == "different"
