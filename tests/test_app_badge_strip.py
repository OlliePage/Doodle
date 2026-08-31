"""Every finished doodle shown fitted to a badge, free, plus a paid redraw.

Doodle can already lay a picture out as an A4 sheet of 58 mm badges. This strip
puts that fit under every result for nothing, since it only re-lays-out what is
already drawn, and offers a redraw composed for the circle as a button that
names its cost. A drawing made for an A4 page puts a small figure in a
landscape the circle then crops the interest out of; a drawing asked for a
badge fills the frame instead, so the redraw is worth its one generation.

The fit is cached by a hash of the picture it was made from, the same shape
colour_previews already uses, so a redraw, a refinement or a swapped
alternative cannot leave a stale one behind: whatever quick_processed now is
gets looked up (or computed) fresh, rather than a separately-tracked value
someone has to remember to update.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, history
from colouring_factory.characters import save_character
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
ARTWORK = (ASSETS / "demo_dinosaur.png").read_bytes()
NEW_ARTWORK = (ASSETS / "demo_bear_astronaut.png").read_bytes()
PDF = b"%PDF-1.4\ntest sheet\n%%EOF\n"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _content_key(image_bytes: bytes) -> str:
    """Mirrors app.py's private _colour_key: sha256 hex of the picture."""

    return hashlib.sha256(image_bytes).hexdigest()


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
    at.run()
    return at


def _button(at: AppTest, label: str):
    for button in at.button:
        if button.label == label:
            return button
    raise AssertionError(f"{label!r} not found; saw {[b.label for b in at.button]}")


def _change_box(at: AppTest):
    for widget in at.text_input:
        if widget.label == "Make a change":
            return widget
    raise AssertionError("the refine box is missing")


def test_the_result_screen_shows_the_doodle_as_a_badge() -> None:
    at = _result_screen()
    assert not at.exception
    captions = " ".join(str(caption.value) for caption in at.caption)
    # Not a bare "badge" check: the Studio-advert caption on this same screen
    # already contains the word "Badges", so that substring alone would pass
    # with no strip at all. The exact size is what only this feature says.
    assert "58 mm badge" in captions.lower()
    assert at.session_state["badge_previews"]


def test_the_redraw_names_its_cost_before_it_is_clicked() -> None:
    at = _result_screen()
    captions = " ".join(str(caption.value) for caption in at.caption)
    # "costs one generation" is the house phrase: the refine box ("Each
    # change costs one generation.") and the colour button both use it.
    assert "costs one generation" in captions.lower()


def test_a_freshly_drawn_doodle_gets_a_free_badge_preview() -> None:
    """The badge cache must actually be reachable from a real drawing.

    A strip that only renders when a test hand-feeds it a picture would
    never appear for a real doodle, so this drives the demo generation path
    end to end and checks a cache entry exists without anything preset.
    """

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["quick_mode"] = "demo"
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["badge_previews"]


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
    assert at.session_state["quick_processed"] is not None
    assert at.session_state["quick_processed"] != ARTWORK
    # The strip below the new doodle must be its own: a cache entry keyed by
    # the new picture, not the old picture's fit left on screen.
    new_key = _content_key(at.session_state["quick_processed"])
    assert new_key in at.session_state["badge_previews"]
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
    errors = " ".join(str(e.value) for e in at.error)
    assert errors


def test_a_new_doodle_shows_no_badge_strip() -> None:
    at = _result_screen()
    at = _button(at, "New doodle").click().run()

    assert not at.exception
    assert at.session_state["quick_processed"] is None
    captions = " ".join(str(c.value) for c in at.caption)
    assert "58 mm badge" not in captions.lower()


def test_a_change_moves_the_picture_and_its_badge(monkeypatch) -> None:
    """ "Change it" must move the picture on screen, and the badge with it.

    _render_refine_controls used to call _set_current_artwork and nothing
    else, so quick_processed (what the result screen and the badge strip
    both read) never moved: the picture on screen looked untouched and any
    badge below it kept showing the rejected original.
    """

    changed = ARTWORK + b"-changed"

    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=changed, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _result_screen()
    at.session_state["doodle_versions"] = history.start(
        GeneratedArtwork(
            image_bytes=ARTWORK,
            prompt="original",
            provider="OpenAI",
            model="gpt-image-2",
        )
    )
    at.session_state["current_version"] = 0
    at.run()

    _change_box(at).set_value("give it a hat")
    at = _button(at, "Change it").click().run()

    assert not at.exception
    assert at.session_state["current_raw"] == changed
    assert at.session_state["quick_processed"] is not None
    assert at.session_state["quick_processed"] != ARTWORK
    new_key = _content_key(at.session_state["quick_processed"])
    assert new_key in at.session_state["badge_previews"]


def test_swapping_an_alternative_moves_the_badge_too() -> None:
    at = _result_screen()
    at.session_state["candidates"] = [
        GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        ),
        GeneratedArtwork(
            image_bytes=NEW_ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        ),
    ]
    at.run()

    at = _button(at, "Use this one").click().run()

    assert not at.exception
    assert at.session_state["current_raw"] == NEW_ARTWORK
    new_key = _content_key(at.session_state["quick_processed"])
    assert new_key in at.session_state["badge_previews"]
