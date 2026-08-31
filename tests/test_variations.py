import json
from io import BytesIO

import pytest

from colouring_factory import variations
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork
from colouring_factory.variations import (
    VARIATION_AXES,
    axis_briefs,
    build_variation_briefs,
    split_pairing_results,
    written_briefs,
)


def _art(tag: str) -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=tag.encode(), prompt=tag, provider="test", model="test"
    )


def test_a_finished_pair_splits_into_one_child_sheet_and_one_grown_up_sheet() -> None:
    child, grown_up = _art("child"), _art("grown-up")
    for_children, pair = split_pairing_results(
        [child, grown_up], pairing=True, total_jobs=2
    )
    assert for_children == [child]
    assert pair is grown_up


def test_stopping_after_only_the_childs_half_of_a_pair_has_no_grown_up_sheet() -> None:
    """Pairing draws exactly two pictures, the second at grown-up detail. If
    the parent stops after only the first has been drawn, there is no
    grown-up sheet to attach — attaching one anyway would print a page
    nobody asked to see next to a caption claiming Doodle drew it."""

    child = _art("child")
    for_children, pair = split_pairing_results([child], pairing=True, total_jobs=2)
    assert for_children == [child]
    assert pair is None


def test_an_ordinary_batch_of_alternatives_has_no_grown_up_sheet() -> None:
    pictures = [_art("one"), _art("two"), _art("three")]
    for_children, pair = split_pairing_results(pictures, pairing=False, total_jobs=4)
    assert for_children == pictures
    assert pair is None


def test_nothing_drawn_yet_splits_into_nothing() -> None:
    for_children, pair = split_pairing_results([], pairing=True, total_jobs=2)
    assert for_children == []
    assert pair is None


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


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_text_reply(text: str) -> _FakeResponse:
    payload = {
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]
    }
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


THREE_BRIEFS = json.dumps(
    [
        "The bear runs across a hilltop, kite string taut behind it.",
        "Close on the bear's face, tongue out, squinting up at the kite.",
        "The bear sits in long grass, the kite tangled in a small tree.",
    ]
)


def test_written_briefs_parses_a_json_list(monkeypatch) -> None:
    monkeypatch.setattr(
        variations,
        "urlopen",
        lambda request, timeout=None: _google_text_reply(THREE_BRIEFS),
    )
    briefs = written_briefs(
        "a bear flying a kite", 3, provider_id="google", api_key="AIza-test"
    )
    assert len(briefs) == 3
    assert "hilltop" in briefs[0]


def test_written_briefs_tolerates_a_fenced_code_block(monkeypatch) -> None:
    fenced = f"```json\n{THREE_BRIEFS}\n```"
    monkeypatch.setattr(
        variations, "urlopen", lambda request, timeout=None: _google_text_reply(fenced)
    )
    assert (
        len(
            written_briefs("a bear flying a kite", 3, provider_id="google", api_key="k")
        )
        == 3
    )


def test_written_briefs_rejects_the_wrong_count(monkeypatch) -> None:
    monkeypatch.setattr(
        variations,
        "urlopen",
        lambda request, timeout=None: _google_text_reply(THREE_BRIEFS),
    )
    with pytest.raises(GeneratorError):
        written_briefs("a bear flying a kite", 4, provider_id="google", api_key="k")


def test_written_briefs_rejects_duplicates(monkeypatch) -> None:
    duplicated = json.dumps(["The bear runs.", "the bear runs", "The bear sits."])
    monkeypatch.setattr(
        variations,
        "urlopen",
        lambda request, timeout=None: _google_text_reply(duplicated),
    )
    with pytest.raises(GeneratorError):
        written_briefs("a bear flying a kite", 3, provider_id="google", api_key="k")


def test_a_provider_without_a_text_model_falls_back_to_axes() -> None:
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="recraft", api_key="token"
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_a_failed_text_call_falls_back_to_axes(monkeypatch) -> None:
    def explode(request, timeout=None):
        raise TimeoutError("no network")

    monkeypatch.setattr(variations, "urlopen", explode)
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="google", api_key="AIza-test"
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_a_malformed_reply_falls_back_to_axes(monkeypatch) -> None:
    monkeypatch.setattr(
        variations,
        "urlopen",
        lambda request, timeout=None: _google_text_reply("not json at all"),
    )
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="google", api_key="AIza-test"
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_a_missing_key_falls_back_to_axes() -> None:
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="google", api_key=""
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_one_alternative_needs_no_text_call(monkeypatch) -> None:
    def explode(request, timeout=None):
        raise AssertionError("no text call should be made for a single picture")

    monkeypatch.setattr(variations, "urlopen", explode)
    assert build_variation_briefs("a bear", 1, provider_id="google", api_key="k") == (
        "a bear",
    )
