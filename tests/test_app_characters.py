"""The characters screen: adding a face to the cast is the caricature feature.

Drawing a character's portrait and drawing a scene are one mechanism with two
doors, so these fixtures (PHOTO_BYTES, the isolation fixture, the screen
builder, _save_two_characters) are shared with tests/test_app_scenes.py and
whatever else joins the cast — written here even where this file's own tests
do not use all of them.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from colouring_factory import generators
from colouring_factory.characters import list_characters, save_character
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


def _one_pixel_png() -> bytes:
    """A real, Pillow-openable photograph stand-in, not just a PNG signature.

    prepare_photo() opens, EXIF-transposes and re-encodes whatever is
    uploaded, so a fake with only the right magic bytes fails inside it
    rather than exercising the path a real phone photo takes.
    """

    buffer = BytesIO()
    Image.new("RGB", (1, 1), (180, 90, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


PHOTO_BYTES = _one_pixel_png()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _characters_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.run()
    return at


def _save_two_characters() -> list[str]:
    """Two characters already in the cast, saved directly through storage.

    Bypasses the drawing screen so a test about an existing cast does not also
    pay for two fake portraits it does not care about.
    """

    return [
        save_character(
            photo=PHOTO_BYTES, portrait=ARTWORK, name=name, kind="person", marks=""
        )
        for name in ("Ida", "Bo")
    ]


def test_the_characters_screen_is_its_own_screen() -> None:
    """The router falls through to Studio for any unknown value.

    Without its own branch a characters screen renders the full Studio and
    nobody notices, so assert on something only this screen shows.
    """

    at = _characters_screen()
    assert not at.exception
    # streamlit==1.62's AppTest has no generic "heading" element type: title,
    # header and subheader are three distinct ones, each with its own
    # accessor, so all three are checked rather than the single family the
    # plan sketched.
    headings = [h.value for h in (*at.title, *at.header, *at.subheader)]
    assert any("character" in str(heading).lower() for heading in headings)
    # The Studio's own controls must not be on this screen.
    assert not [radio for radio in at.radio if radio.label == "Artwork source"]


def test_adding_a_character_draws_a_portrait_and_saves_it(monkeypatch) -> None:
    def fake_refine(**kwargs):
        assert kwargs["reference_images"]
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    # Patched on colouring_factory.generators, not on app itself: AppTest
    # re-executes app.py's whole module body, imports included, on every
    # .run(), so a patch on app.refine_with_provider is silently undone by
    # the next widget interaction's re-import. Patching the source the
    # import pulls from survives every rerun.
    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    at.text_area(key="character_marks").set_value("Curly hair, round glasses.").run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert [c.name for c in list_characters()] == ["Ida"]
    # The portrait is a doodle like any other, so it lands on the result screen.
    assert at.session_state["screen"] == "result"
    assert at.session_state["quick_processed"]


def test_a_caricature_is_drawn_at_the_providers_square_size(monkeypatch) -> None:
    """A caricature is a face, and a face is the most badge-shaped thing
    Doodle draws, so it is drawn square rather than portrait. Nothing else
    in the suite pins this down: swap `square_size` for `portrait_size` in
    `_draw_character_portrait` and every other test here stays green."""

    from colouring_factory.providers import get_provider

    captured = {}

    def fake_refine(**kwargs):
        captured["size"] = kwargs["size"]
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    at.text_area(key="character_marks").set_value("Curly hair, round glasses.").run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert captured["size"] == get_provider("openai").square_size


def test_a_declined_photograph_is_explained_as_a_picture_problem(monkeypatch) -> None:
    def refuse(**kwargs):
        raise GeneratorError(
            "OpenAI would not draw from that picture.",
            provider="OpenAI",
            code="photo_declined",
        )

    monkeypatch.setattr(generators, "refine_with_provider", refuse)
    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    at.text_area(key="character_marks").set_value("Curly hair, round glasses.").run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    # _show_guidance splits the message across st.error (title + detail) and,
    # inside its own container, st.markdown (the fix) and st.caption (the
    # control) — the wrong-screen advice this guards against lives in the
    # latter two, not in the error line itself.
    guidance_text = " ".join(
        str(element.value)
        for group in (at.error, at.markdown, at.caption)
        for element in group
    )
    assert "picture" in guidance_text.lower()
    # The old content guidance blamed the wording and pointed at the idea box.
    assert "television" not in guidance_text.lower()
    # A parent on the character-creation screen has nothing to untick, and
    # is not standing on the homepage — the fix given here must be true on
    # both screens this code can fire from, not just the one it was written
    # for.
    assert "untick" not in guidance_text.lower()
    assert "homepage" not in guidance_text.lower()
    assert list_characters() == []


def test_a_character_with_no_name_is_not_drawn(monkeypatch) -> None:
    """A wasted generation is worse than a blank name being refused up front."""

    calls = []
    monkeypatch.setattr(
        generators, "refine_with_provider", lambda **kwargs: calls.append(kwargs)
    )

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert not calls
    assert list_characters() == []


def test_the_back_button_returns_to_where_the_screen_was_opened_from() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.session_state["characters_return"] = "result"
    at.run()

    for button in at.button:
        if button.label == "Back":
            button.click().run()
            break
    else:
        raise AssertionError("Back button not found")

    assert not at.exception
    assert at.session_state["screen"] == "result"


def test_deleting_a_character_needs_a_second_click() -> None:
    ida_id, _bo_id = _save_two_characters()

    at = _characters_screen()
    for button in at.button:
        if button.key == f"delete_character_{ida_id}":
            button.click().run()
            break
    else:
        raise AssertionError("Delete button for Ida not found")

    # Newest first, so Bo (saved second) leads.
    assert [c.name for c in list_characters()] == ["Bo", "Ida"]
    warnings = [str(w.value) for w in at.warning]
    assert any("delete" in warning.lower() for warning in warnings)

    for button in at.button:
        if button.key == f"confirm_delete_character_{ida_id}":
            button.click().run()
            break
    else:
        raise AssertionError("Confirm delete button not found")

    assert [c.name for c in list_characters()] == ["Bo"]


def test_starting_a_new_doodle_keeps_the_chosen_cast_but_clears_the_draft() -> None:
    """A parent drawing for the same children wants the same cast next time,
    the same reasoning the homepage settings already follow."""

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.session_state["chosen_characters"] = ["someone"]
    at.session_state["character_draft"] = {"name": "Half-typed"}
    at.run()

    for button in at.button:
        if button.label == "New doodle":
            button.click().run()
            break
    else:
        raise AssertionError("New doodle button not found")

    assert at.session_state["screen"] == "home"
    assert at.session_state["chosen_characters"] == ["someone"]
    assert at.session_state["character_draft"] == {}
