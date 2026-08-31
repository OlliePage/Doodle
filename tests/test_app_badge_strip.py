"""Every finished doodle shown fitted to a badge, free, plus a paid redraw.

Doodle can already lay a picture out as an A4 sheet of 58 mm badges. This strip
puts that fit under every result for nothing, since it only re-lays-out what is
already drawn, and offers a redraw composed for the circle as a button that
names its cost. A drawing made for an A4 page puts a small figure in a
landscape the circle then crops the interest out of; a drawing asked for a
badge fills the frame instead, so the redraw is worth its one generation.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators
from colouring_factory.characters import save_character
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
ARTWORK = (ASSETS / "demo_dinosaur.png").read_bytes()
NEW_ARTWORK = (ASSETS / "demo_bear_astronaut.png").read_bytes()
BADGE_PREVIEW = (ASSETS / "demo_robot_balloons.png").read_bytes()
PDF = b"%PDF-1.4\ntest sheet\n%%EOF\n"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = PDF
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {
        "source": "test",
        "concept": "Blue dinosaur",
    }
    # Already-prepared, the same convention test_app_print.py's quick_pdf
    # fake follows: this file's job is the strip's render and wiring, not
    # re-proving the fitting maths _cached_badge_preview already owns.
    at.session_state["badge_preview"] = BADGE_PREVIEW
    at.session_state["badge_raw"] = ARTWORK
    at.run()
    return at


def _button(at: AppTest, label: str):
    for button in at.button:
        if button.label == label:
            return button
    raise AssertionError(f"{label!r} not found; saw {[b.label for b in at.button]}")


def test_the_result_screen_shows_the_doodle_as_a_badge() -> None:
    at = _result_screen()
    assert not at.exception
    captions = " ".join(str(caption.value) for caption in at.caption)
    # Not a bare "badge" check: the Studio-advert caption on this same screen
    # already contains the word "Badges", so that substring alone would pass
    # with no strip at all. The exact size is what only this feature says.
    assert "58 mm badge" in captions.lower()
    assert at.session_state["badge_preview"]


def test_the_redraw_names_its_cost_before_it_is_clicked() -> None:
    at = _result_screen()
    captions = " ".join(str(caption.value) for caption in at.caption)
    assert "costs one drawing" in captions.lower()


def test_a_freshly_drawn_doodle_gets_a_free_badge_preview() -> None:
    """_prepare_badge_outputs must actually be wired into _quick_generate.

    A strip that only renders when a test hand-feeds it badge_preview would
    never appear for a real doodle, so this drives the demo generation path
    end to end and checks the key is populated without being preset.
    """

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["quick_mode"] = "demo"
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["badge_preview"]


def test_drawing_it_for_a_badge_asks_for_a_square_composed_picture(monkeypatch) -> None:
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return [
            GeneratedArtwork(
                image_bytes=NEW_ARTWORK,
                prompt="p",
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    # Patched on colouring_factory.generators, not on app itself: AppTest
    # re-executes app.py's whole module body, imports included, on every
    # .run(), so a patch on app.generate_with_provider is silently undone by
    # the next widget interaction's re-import.
    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)

    at = _result_screen()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    # A picture composed for a page puts a small figure in a landscape the
    # circle then cuts away, so the redraw asks for square and for corners.
    assert captured["size"] == "1024x1024"
    assert "cut into a circle" in captured["prompts"][0]


def test_the_redraw_adopts_the_new_picture_as_the_doodle(monkeypatch) -> None:
    def fake_generate(**kwargs):
        return [
            GeneratedArtwork(
                image_bytes=NEW_ARTWORK,
                prompt="p",
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)

    at = _result_screen()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    assert at.session_state["current_raw"] == NEW_ARTWORK
    assert at.session_state["badge_raw"] == NEW_ARTWORK
    assert at.session_state["quick_processed"] is not None
    # The strip below the new doodle must be its own, not the old picture's
    # fit left on screen.
    assert at.session_state["badge_preview"] != BADGE_PREVIEW
    # A redraw starts a fresh doodle rather than appending to the picture it
    # replaced, the same rule _adopt_artwork already applies everywhere else.
    assert len(at.session_state["doodle_versions"]) == 1
    assert at.session_state["candidates"] == []


def test_a_chosen_cast_keeps_their_likeness_on_the_badge(monkeypatch) -> None:
    """A badge of a scene starring your daughter must still star your
    daughter, so the redraw uses the character scene builder and the saved
    portraits, not the ordinary colouring prompt."""

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=NEW_ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    save_character(
        photo=b"photo", portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _result_screen()
    at.session_state["chosen_characters"] = ["Ida"]
    at.run()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    assert len(captured["reference_images"]) == 1
    assert captured["size"] == "1024x1024"
    assert "Ida" in captured["prompt"]
    assert "cut into a circle" in captured["prompt"]


def test_a_failed_redraw_is_explained_rather_than_crashing(monkeypatch) -> None:
    def refuse(**kwargs):
        raise GeneratorError(
            "OpenAI would not draw that idea.", provider="OpenAI", code="content"
        )

    monkeypatch.setattr(generators, "generate_with_provider", refuse)

    at = _result_screen()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    # A declined redraw must not touch the doodle already on screen.
    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["badge_raw"] == ARTWORK
    errors = " ".join(str(e.value) for e in at.error)
    assert errors


def test_starting_a_new_doodle_clears_the_badge_strip() -> None:
    at = _result_screen()
    at = _button(at, "New doodle").click().run()

    assert not at.exception
    assert at.session_state["badge_preview"] is None
    assert at.session_state["badge_raw"] is None
