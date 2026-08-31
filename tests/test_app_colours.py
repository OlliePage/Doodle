"""Seeing a doodle coloured in, without colouring what gets printed.

A page of outlines tells a child nothing about what colour water or grass
should be. This draws one coloured copy to compare against; the PDF stays
black and white, and these tests hold that line.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators
from colouring_factory.characters import save_character
from colouring_factory.models import GeneratedArtwork

APPEARANCE = "Brown eyes, wavy dark-brown hair to her shoulders, light-brown skin."
PHOTO = b"\x89PNG\r\n\x1a\n" + b"photo bytes"


def _save_ida() -> str:
    return save_character(
        photo=PHOTO,
        portrait=COLOURED,
        name="Ida",
        kind="person",
        marks="",
        appearance=APPEARANCE,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
LINE_ART = (ASSETS / "demo_dinosaur.png").read_bytes()
# A different picture for the grown-up half of a pair, so the two sheets
# cannot be confused for one another in an assertion.
OTHER_LINE_ART = (ASSETS / "demo_robot_balloons.png").read_bytes()
COLOURED = (ASSETS / "demo_robot_balloons.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


@pytest.fixture
def coloured(monkeypatch):
    calls: list[dict] = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        return GeneratedArtwork(
            image_bytes=COLOURED,
            prompt=kwargs["prompt"],
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    return calls


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _has_button(at: AppTest, fragment: str) -> bool:
    return any(fragment.lower() in button.label.lower() for button in at.button)


def _captions(at: AppTest) -> str:
    return " ".join(caption.value for caption in at.caption)


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = LINE_ART
    at.session_state["quick_processed"] = LINE_ART
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def _paired_result_screen(monkeypatch) -> AppTest:
    """A result screen holding both sheets of a pair.

    The grown-up half is whatever was drawn second; the screen only needs its
    processed picture and its PDF to render it.
    """

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = LINE_ART
    at.session_state["quick_processed"] = LINE_ART
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["pair_processed"] = OTHER_LINE_ART
    at.session_state["pair_pdf"] = b"%PDF-1.4 grown-up"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def test_the_offer_to_colour_it_in_is_on_the_result_screen() -> None:
    at = _result_screen()
    assert not at.exception
    assert _has_button(at, "colour it in for me")


def test_colouring_it_in_shows_the_coloured_copy(coloured) -> None:
    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    assert len(coloured) == 1, "one generation, not one per rerun"
    assert at.session_state["showing_colours_result"] is True
    assert COLOURED in at.session_state["colour_previews"].values()
    assert "black and white" in _captions(at)


def test_the_printed_pdf_is_never_the_coloured_one(coloured) -> None:
    at = _result_screen()
    before = at.session_state["quick_pdf"]

    at = _button(at, "colour it in for me").click().run()
    assert at.session_state["quick_pdf"] == before
    assert at.session_state["quick_processed"] == LINE_ART


def test_the_outlines_come_back(coloured) -> None:
    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    at = _button(at, "show the outlines").click().run()
    assert not at.exception
    assert at.session_state["showing_colours_result"] is False
    assert _has_button(at, "show suggested colours")


def test_looking_again_costs_nothing(coloured) -> None:
    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()
    at = _button(at, "show the outlines").click().run()
    at = _button(at, "show suggested colours").click().run()

    assert not at.exception
    assert at.session_state["showing_colours_result"] is True
    assert len(coloured) == 1, "the coloured copy is kept, not redrawn"


def test_the_instruction_asks_to_keep_the_drawing_intact(coloured) -> None:
    at = _result_screen()
    _button(at, "colour it in for me").click().run()

    instruction = " ".join(coloured[0]["prompt"].lower().split())
    assert "keep every black outline" in instruction
    assert "do not redraw" in instruction
    # Named colours a child can check against the real thing.
    assert "green" in instruction
    assert "blue" in instruction


def test_a_failed_attempt_explains_itself_and_keeps_the_picture(monkeypatch) -> None:
    def failing(**kwargs):
        raise generators.GeneratorError(
            "OpenAI refused that request.", provider="OpenAI", code="content"
        )

    monkeypatch.setattr(generators, "refine_with_provider", failing)

    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    assert at.session_state["showing_colours_result"] is False
    assert at.session_state["colour_previews"] == {}
    assert at.session_state["quick_processed"] == LINE_ART


def test_a_click_while_already_in_flight_colours_nothing_more(coloured) -> None:
    """Streamlit can queue a click made while this control's own previous
    press is still blocked in the drawing service's call, and replay it the
    instant that call returns — a second generation from one press."""

    at = _result_screen()
    at.session_state["busy_colour_result"] = True
    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    assert coloured == []
    assert at.session_state["colour_previews"] == {}


def test_a_failed_attempt_leaves_the_control_pressable_again(monkeypatch) -> None:
    def failing(**kwargs):
        raise generators.GeneratorError(
            "OpenAI refused that request.", provider="OpenAI", code="content"
        )

    monkeypatch.setattr(generators, "refine_with_provider", failing)

    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    assert at.session_state["busy_colour_result"] is False


def test_a_recorded_characters_appearance_reaches_the_colouring_instruction(
    coloured,
) -> None:
    """The bug this whole feature exists for: a picture drawn with a saved
    character must be coloured using their real hair, eyes and skin — read
    from the artwork's own recorded cast, the same source the badge redraw
    uses, never from whichever characters happen to be ticked now."""

    ida_id = _save_ida()

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = LINE_ART
    at.session_state["quick_processed"] = LINE_ART
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["current_title"] = "Ida in the garden"
    at.session_state["current_metadata"] = {
        "source": "test",
        "generation": {"characters": [ida_id]},
    }
    at.run()

    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    instruction = coloured[0]["prompt"]
    assert "Ida" in instruction
    assert APPEARANCE in instruction


def test_ticking_a_character_now_does_not_colour_a_picture_drawn_without_them(
    coloured,
) -> None:
    """The tick list on the homepage is not the source: a picture with no
    recorded cast (an ordinary idea, or a sample) must colour exactly as it
    always has, whoever happens to be ticked at the moment the button is
    pressed."""

    ida_id = _save_ida()

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = LINE_ART
    at.session_state["quick_processed"] = LINE_ART
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["chosen_characters"] = [ida_id]
    at.run()

    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    instruction = coloured[0]["prompt"]
    assert "Ida" not in instruction
    assert APPEARANCE not in instruction


def test_the_grown_up_sheet_gets_a_colour_guide_of_its_own(monkeypatch) -> None:
    """Offering one only on the children's sheet left the more detailed of the
    two — the one whose many small regions most need a suggestion — with
    nothing to copy from."""

    at = _paired_result_screen(monkeypatch)
    assert not at.exception

    keys = [button.key for button in at.button if button.key]
    assert any(key.startswith("result_") and "colour" in key for key in keys), (
        f"the children's sheet has no colour control: {keys}"
    )
    assert any(key.startswith("grown_up_") and "colour" in key for key in keys), (
        f"the grown-up sheet has no colour control: {keys}"
    )


def test_showing_colours_on_one_sheet_leaves_the_other_alone(
    monkeypatch, coloured
) -> None:
    """One shared flag meant colouring one sheet coloured the other, and a pair
    is two pictures a parent may well want to look at differently."""

    at = _paired_result_screen(monkeypatch)

    assert at.session_state["showing_colours_result"] is False
    assert at.session_state["showing_colours_grown_up"] is False

    for button in at.button:
        if button.key == "result_make_colours":
            button.click().run()
            break
    else:
        raise AssertionError("the children's sheet had no colour button")

    assert not at.exception
    assert at.session_state["showing_colours_result"] is True
    assert at.session_state["showing_colours_grown_up"] is False, (
        "colouring one sheet coloured the other"
    )


def test_the_grown_up_guide_asks_for_more_shades() -> None:
    """A child's page usually gives one shape one colour. A grown-up page has
    divided the same objects into many small regions, and filling every one of
    them the same flat green wastes what the drawing is for."""

    from colouring_factory.prompts import build_colour_suggestion_prompt

    child = build_colour_suggestion_prompt()
    grown_up = build_colour_suggestion_prompt(detailed=True)

    assert "flat, bright, friendly colour" in child
    assert "family of related shades" in grown_up
    assert "several greens across the" in grown_up
    assert "several blues across the panels of one balloon" in grown_up
    # Both still refuse the thing that stops a page being copyable.
    for prompt in (child, grown_up):
        assert "gradients" in prompt
        assert "Keep every black outline exactly where it is" in prompt


def test_a_pair_stands_side_by_side_and_the_page_makes_room(monkeypatch) -> None:
    """One sheet under the other made a pair a long scroll, and comparing them
    is the whole point of a pair. The result screen pinned itself to 800px
    however wide the window was."""

    at = _paired_result_screen(monkeypatch)
    assert not at.exception

    def columns_holding(node, inside=False, found=None):
        found = [] if found is None else found
        for child in getattr(node, "children", {}).values():
            kind = getattr(child, "type", type(child).__name__)
            if type(child).__name__ == "Image" and inside:
                found.append(True)
            columns_holding(child, inside or kind == "column", found)
        return found

    assert len(columns_holding(at.main)) >= 2, (
        "the two sheets are not in columns beside each other"
    )

    styles = " ".join(str(block.value) for block in at.markdown)
    assert "max-width:1360px" in styles, (
        "the result screen did not widen to make room for two sheets"
    )


def test_a_single_doodle_keeps_the_narrow_column() -> None:
    """A page you can take in at a glance is better for one picture; the width
    is for the pair, not for everything."""

    at = _result_screen()
    styles = " ".join(str(block.value) for block in at.markdown)
    assert "max-width:800px" in styles
