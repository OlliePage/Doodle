"""Choosing how a doodle is drawn before paying for it, and getting back out.

Pressing Enter on the homepage went straight to one picture on fixed settings,
with the controls for them inside Doodle Studio, behind the drawing that had
already been made. Starting a fresh doodle meant scrolling to the very bottom
of the result screen.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import load_settings, quick_drawing_options

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
ARTWORK = (ASSETS / "demo_dinosaur.png").read_bytes()
OTHER = (ASSETS / "demo_robot_balloons.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


@pytest.fixture
def drawn(monkeypatch):
    """Draw fixed pictures instead of calling a provider."""

    images = [ARTWORK, OTHER, ARTWORK, OTHER]

    def fake_generate(**kwargs):
        return [
            GeneratedArtwork(
                image_bytes=images[index % len(images)],
                prompt=prompt,
                provider="OpenAI",
                model="gpt-image-2",
            )
            for index, prompt in enumerate(kwargs["prompts"])
        ]

    def fake_briefs(idea, count, **kwargs):
        return [f"reading {index + 1} of {idea}" for index in range(count)]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", fake_briefs)


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _has_button(at: AppTest, fragment: str) -> bool:
    return any(fragment.lower() in button.label.lower() for button in at.button)


def _homepage() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def test_the_homepage_offers_the_drawing_options_before_it_draws() -> None:
    at = _homepage()
    assert not at.exception

    labels = [control.label for control in at.segmented_control]
    assert "How many to draw" in labels
    assert "Who it is for" in labels
    assert any(box.label == "Drawing style" for box in at.selectbox)


def test_the_number_of_pictures_is_remembered_between_visits() -> None:
    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(3).run()
    assert not at.exception
    assert quick_drawing_options(load_settings())["alternatives"] == 3

    fresh = _homepage()
    assert quick_drawing_options(load_settings())["alternatives"] == 3
    assert not fresh.exception


def test_the_collapsed_options_say_what_will_happen() -> None:
    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(3).run()
    headings = " ".join(
        str(block.proto.label)
        for block in at.main.children.values()
        if getattr(block, "type", "") == "expander"
    )
    assert "3 pictures" in headings


def test_asking_for_three_draws_three_and_offers_the_choice(drawn) -> None:
    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(3).run()

    at.text_input(key="home_prompt").set_value("a dinosaur washing a fire engine")
    at = _button(at, "draw it").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert len(at.session_state["candidates"]) == 3

    captions = " ".join(caption.value for caption in at.caption)
    assert "same idea" in captions


def test_one_picture_asks_for_no_plan_and_offers_no_choice(drawn) -> None:
    at = _homepage()
    at.text_input(key="home_prompt").set_value("a rocket")
    at = _button(at, "draw it").click().run()

    assert at.session_state["screen"] == "result"
    assert at.session_state["candidates"] == []
    assert not _has_button(at, "use this one")


def test_choosing_another_picture_changes_what_is_shown_and_printed(drawn) -> None:
    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(2).run()
    at.text_input(key="home_prompt").set_value("a dinosaur washing a fire engine")
    at = _button(at, "draw it").click().run()

    first_pdf = at.session_state["quick_pdf"]
    assert at.session_state["current_raw"] == ARTWORK

    at = _button(at, "use this one").click().run()
    assert not at.exception
    assert at.session_state["current_raw"] == OTHER
    assert at.session_state["quick_pdf"] != first_pdf


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def test_a_new_doodle_is_one_click_from_the_top_of_the_result_screen() -> None:
    at = _result_screen()
    assert not at.exception

    at = _button(at, "new doodle").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert at.session_state["current_raw"] is None


def test_the_saved_route_is_offered_before_anything_is_saved() -> None:
    at = _result_screen()
    saved = _button(at, "saved")
    assert saved.disabled, "nothing is saved yet, so there is nowhere to go"

    at = _button(at, "save to your doodles").click().run()
    at = _button(at, "saved (1)").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "library"


def test_the_studio_carries_the_same_two_routes() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()

    assert not at.exception
    assert _has_button(at, "new doodle")
    assert _has_button(at, "saved")
