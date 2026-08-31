"""Four levels of detail, and one idea drawn at two of them at once.

A toddler's sheet and an adult's sheet are different drawings of the same
scene, so the family can colour the same picture together. These tests hold
the two halves that make that true: the levels really do ask for different
drawings, and the pair really is one scene rendered twice.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.models import GeneratedArtwork
from colouring_factory.prompts import DETAIL_LEVELS, build_colouring_prompt
from colouring_factory.storage import (
    QUICK_AGE_CHOICES,
    load_settings,
    quick_drawing_options,
    save_settings,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
CHILD_ART = (ASSETS / "demo_dinosaur.png").read_bytes()
GROWN_UP_ART = (ASSETS / "demo_robot_balloons.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _words(text: str) -> str:
    return " ".join(text.lower().split())


def test_every_level_is_offered_and_the_grown_up_one_is_last() -> None:
    assert QUICK_AGE_CHOICES == ("2-3 years", "4-5 years", "6-9 years", "Grown-up")
    assert set(QUICK_AGE_CHOICES) == set(DETAIL_LEVELS)


def test_the_levels_ask_for_visibly_different_drawings() -> None:
    prompts = {
        level: _words(build_colouring_prompt("a fox in a wood", age_profile=level))
        for level in QUICK_AGE_CHOICES
    }
    assert len(set(prompts.values())) == 4, "two levels ask for the same drawing"

    assert "6 to 12 large colouring regions" in prompts["2-3 years"]
    assert "12 to 28 colouring regions" in prompts["4-5 years"]
    assert "30 to 60 colouring regions" in prompts["6-9 years"]
    assert "150 or more small colouring regions" in prompts["Grown-up"]


def test_the_grown_up_sheet_is_drawn_for_an_adult() -> None:
    grown_up = _words(build_colouring_prompt("a fox in a wood", age_profile="Grown-up"))

    assert "for an adult who colours to unwind" in grown_up
    assert "toddler" not in grown_up and "preschool" not in grown_up
    # The density is the whole point of an adult colouring page.
    assert "mandala or zentangle" in grown_up
    assert "dense decorative pattern" in grown_up


def test_a_grown_up_sheet_is_still_something_you_can_colour() -> None:
    """Intricate, but never filled in or shaded: it has to take a pencil."""

    grown_up = _words(build_colouring_prompt("a fox in a wood", age_profile="Grown-up"))

    assert "no colour, grey, shading, shadows, gradients or hatching" in grown_up
    assert "every enclosed shape must be left white" in grown_up
    assert "never a shaded or filled black mass" in grown_up


def test_a_toddler_sheet_is_still_kept_plain() -> None:
    toddler = _words(build_colouring_prompt("a fox in a wood", age_profile="2-3 years"))
    assert "no pattern, texture or fill of any kind" in toddler
    assert "mandala" not in toddler


def test_an_unknown_level_falls_back_to_the_youngest() -> None:
    assert quick_drawing_options({"quick_age_profile": "17 years"})["age_profile"] == (
        "2-3 years"
    )
    invented = build_colouring_prompt("a fox", age_profile="17 years")
    assert "6 to 12 large colouring regions" in _words(invented)


def test_a_grown_up_drawing_for_themselves_is_never_paired() -> None:
    """Pairing a grown-up sheet with a grown-up sheet is the same page twice."""

    options = quick_drawing_options(
        {"quick_age_profile": "Grown-up", "quick_pair_grown_up": True}
    )
    assert options["pair_grown_up"] is False


@pytest.fixture
def drawn(monkeypatch):
    """Record what was asked for, and answer with two distinguishable pictures.

    Each picture is now its own call to generate_with_provider rather than
    one entry in a prompts list handed to a single call, so which image
    comes back is picked from the detail level baked into that job's own
    prompt — the phrase only a grown-up sheet's prompt carries — rather
    than from its position in a shared list.
    """

    class Asked(list):
        """The prompts, with the reference pictures recorded alongside them."""

        references: list[tuple]

    asked = Asked()
    references: list[tuple] = []

    def _answer(prompt: str) -> GeneratedArtwork:
        is_grown_up = "150 or more small colouring regions" in prompt
        return GeneratedArtwork(
            image_bytes=GROWN_UP_ART if is_grown_up else CHILD_ART,
            prompt=prompt,
            provider="OpenAI",
            model="gpt-image-2",
        )

    def fake_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        asked.append(prompt)
        return [_answer(prompt)]

    # The pair's second sheet is drawn FROM the first since 2026-08-31, so it
    # goes through the reference-carrying call and this fixture has to watch
    # both doors. Watching only the text-only one made a two-sheet batch look
    # like a one-sheet batch.
    def fake_refine(**kwargs):
        prompt = kwargs["prompt"]
        asked.append(prompt)
        references.append(tuple(kwargs.get("reference_images") or ()))
        return _answer(prompt)

    def fake_briefs(idea, count, **kwargs):
        return [f"reading {index + 1} of {idea}" for index in range(count)]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    monkeypatch.setattr(variations, "build_variation_briefs", fake_briefs)
    asked.references = references
    return asked


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _has_button(at: AppTest, fragment: str) -> bool:
    return any(fragment.lower() in button.label.lower() for button in at.button)


def _draw(pair: bool, *, alternatives: int = 1) -> AppTest:
    save_settings(
        {
            **load_settings(),
            "quick_alternatives": alternatives,
            "quick_age_profile": "2-3 years",
            "quick_pair_grown_up": pair,
        }
    )
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.text_input(key="home_prompt").set_value("a fox in a wood")
    return _button(at, "draw it").click().run()


def test_ticking_the_box_draws_the_same_scene_twice(drawn) -> None:
    at = _draw(pair=True)
    assert not at.exception

    assert len(drawn) == 2, "one sheet for them, one for you"
    children, grown_up = (_words(prompt) for prompt in drawn)
    assert "6 to 12 large colouring regions" in children
    assert "150 or more small colouring regions" in grown_up

    # One scene, described identically, so the two sheets show the same picture.
    assert "scene: a fox in a wood" in children
    assert "scene: a fox in a wood" in grown_up


def test_both_sheets_are_printable_and_separate(drawn) -> None:
    at = _draw(pair=True)

    assert at.session_state["quick_processed"] is not None
    assert at.session_state["pair_processed"] is not None
    assert at.session_state["quick_pdf"] != at.session_state["pair_pdf"]
    assert _has_button(at, "print this doodle")
    assert _has_button(at, "print your sheet")


def test_the_childrens_sheet_is_the_one_everything_else_acts_on(drawn) -> None:
    at = _draw(pair=True)

    assert at.session_state["current_raw"] == CHILD_ART
    assert at.session_state["pair_raw"] == GROWN_UP_ART
    # The grown-up sheet is a second print, not an alternative to choose between.
    assert at.session_state["candidates"] == []
    assert not _has_button(at, "use this one")


def test_a_pair_costs_two_pictures_whatever_the_alternatives_say(drawn) -> None:
    at = _draw(pair=True, alternatives=4)

    assert len(drawn) == 2
    assert at.session_state["candidates"] == []
    assert not at.exception


def test_without_the_tick_nothing_changes(drawn) -> None:
    at = _draw(pair=False)

    assert len(drawn) == 1
    assert at.session_state["pair_raw"] is None
    assert not _has_button(at, "print your sheet")


def _popover_labels(at: AppTest) -> str:
    found: list[str] = []

    def walk(block):
        if getattr(block, "type", "") == "popover":
            found.append(block.proto.popover.label)
        for child in getattr(block, "children", {}).values():
            walk(child)

    walk(at.main)
    return " ".join(found)


def test_the_settings_line_says_when_a_second_sheet_is_coming() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert "+ grown-up" not in _popover_labels(at)

    at = at.checkbox(key="home_pair_grown_up").set_value(True).run()
    assert not at.exception
    assert "2-3 years + grown-up" in _popover_labels(at)
    assert quick_drawing_options(load_settings())["pair_grown_up"] is True


def test_the_offer_disappears_when_the_sheet_is_already_yours() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert at.checkbox(key="home_pair_grown_up")

    at = at.segmented_control(key="home_age_profile").set_value("Grown-up").run()
    assert not at.exception
    assert not at.checkbox, "nothing to pair a grown-up sheet with"


def test_starting_a_new_doodle_clears_the_grown_up_sheet(drawn) -> None:
    at = _draw(pair=True)
    at = _button(at, "new doodle").click().run()

    assert not at.exception
    assert at.session_state["pair_raw"] is None
    assert at.session_state["pair_pdf"] is None


def test_the_grown_up_sheet_is_drawn_from_the_childrens_one(drawn) -> None:
    """Both sheets used to be drawn from the same words and hoped to match.
    Reported 2026-08-31: a picnic under a hot air balloon festival came back as
    two different pictures — different clothes, different food, different
    composition — under a caption promising the same scene."""

    at = _draw(True)
    assert not at.exception
    assert len(drawn) == 2

    attached = drawn.references
    assert attached, "the second sheet was drawn from words again, not the first"
    assert CHILD_ART in attached[0], (
        "the grown-up sheet was not given the children's sheet to work from"
    )


def test_the_second_sheet_is_told_to_change_only_the_detail(drawn) -> None:
    """Told only to add detail, a model redraws the scene its own way and then
    decorates that. Sameness has to come first."""

    _draw(True)
    grown_up = drawn[1]

    assert "The attached picture is a colouring page of this same scene" in grown_up
    assert "Nothing may be added, removed, moved or resized" in grown_up
    assert "one picture drawn twice" in grown_up
