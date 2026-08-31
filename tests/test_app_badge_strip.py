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
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
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
    portraits, not the ordinary colouring prompt.

    The doodle on screen is recorded as having been drawn with Ida, the way
    _quick_generate actually records it, rather than relied on by ticking
    her live on the result screen — see the next test for why that
    distinction matters.
    """

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=NEW_ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id = save_character(
        photo=b"photo", portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _result_screen()
    at.session_state["current_metadata"] = {
        **at.session_state["current_metadata"],
        "generation": {"characters": [ida_id]},
    }
    at.run()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    assert len(captured["reference_images"]) == 1
    assert captured["size"] == "1024x1024"
    assert "Ida" in captured["prompt"]
    assert "cut into a circle" in captured["prompt"]


def test_the_badge_redraw_sends_the_photograph_not_the_caricature(monkeypatch) -> None:
    """FB-03: the badge redraw must send the same likeness reference the
    scene path does — the stored photograph, not the deliberately
    exaggerated portrait — or a badge composed from a scene starring a
    character draws that character's caricature back at the provider
    instead of the child or toy the caricature was drawn from."""

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=NEW_ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id = save_character(
        photo=b"photo", portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _result_screen()
    at.session_state["current_metadata"] = {
        **at.session_state["current_metadata"],
        "generation": {"characters": [ida_id]},
    }
    at.run()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    assert captured["reference_images"] == (b"photo",)
    assert ARTWORK not in captured["reference_images"]


def test_pressing_the_badge_redraw_twice_keeps_the_cast_on_the_second_press(
    monkeypatch,
) -> None:
    """FB-04: _adopt_artwork used to overwrite current_metadata["generation"]
    wholesale with the fresh artwork's own metadata, which carries no
    "characters" key. The first press of "Draw it for a badge" read the
    recorded cast correctly and then destroyed it in the act of adopting its
    own result, so a second press — the exact button a parent presses again
    after not liking the first circle composition — silently dropped the
    character and spent a generation on somebody else's picture."""

    calls = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        return GeneratedArtwork(
            image_bytes=NEW_ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    monkeypatch.setattr(
        generators,
        "generate_with_provider",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError(
                "a picture drawn with a recorded cast must not fall through "
                "to the no-cast, no-reference generation path"
            )
        ),
    )
    ida_id = save_character(
        photo=b"photo", portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _result_screen()
    at.session_state["current_metadata"] = {
        **at.session_state["current_metadata"],
        "generation": {"characters": [ida_id]},
    }
    at.run()

    at = _button(at, "Draw it for a badge").click().run()
    assert not at.exception
    assert "Ida" in calls[0]["prompt"]

    at = _button(at, "Draw it for a badge").click().run()
    assert not at.exception
    assert len(calls) == 2, "the second press must still call refine_with_provider"
    assert "Ida" in calls[1]["prompt"], (
        "the cast was lost between the first and second badge redraw"
    )
    assert calls[1]["reference_images"]


def test_redrawing_a_character_portrait_for_a_badge_keeps_the_character(
    monkeypatch,
) -> None:
    """FB-04, second repro: the characters screen adopted a freshly drawn
    caricature without recording the very character it is a caricature of,
    so pressing "Draw it for a badge" on that portrait sent the provider a
    bare name with no reference picture attached at all — the one picture
    whose badge redraw could least afford to lose its cast. (Which of the
    character's two pictures is the right one to send is FB-03's concern,
    covered separately — this test only needs a reference attached at all.)
    """

    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id = save_character(
        photo=b"photo", portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _result_screen()
    # A character portrait's own adoption path: no scene idea, the cast is
    # just the character themselves.
    at.session_state["current_metadata"] = {
        "source": "OpenAI",
        "concept": "Ida, drawn by Doodle",
        "generation": {"characters": [ida_id]},
    }
    at.run()

    captured = {}
    monkeypatch.setattr(
        generators,
        "refine_with_provider",
        lambda **kwargs: captured.update(kwargs) or fake_refine(**kwargs),
    )
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    assert len(captured["reference_images"]) == 1, (
        "the character's cast was lost, so no reference picture was sent"
    )
    assert "Ida" in captured["prompt"]


def test_ticking_a_character_now_does_not_put_them_in_a_picture_drawn_without_them(
    monkeypatch,
) -> None:
    """IMPORTANT: app.py:2040 used to read the live tick list at redraw
    time, so the badge strip under a picture drawn with no cast at all — a
    built-in sample among them — would still draw whoever happened to be
    ticked when the button was pressed. That is one paid drawing spent
    putting someone into a picture that never had them. The redraw must use
    who the doodle was actually drawn with (nobody, here), never who is
    ticked now."""

    def fail_if_called(**kwargs):
        raise AssertionError(
            "a picture drawn with no cast must not go through refine_with_provider"
        )

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

    monkeypatch.setattr(generators, "refine_with_provider", fail_if_called)
    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    ida_id = save_character(
        photo=b"photo", portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    # The sample dinosaur, drawn with no cast: current_metadata carries no
    # "generation" -> "characters" entry, exactly what a real demo drawing
    # produces.
    at = _result_screen()
    # Ticked after the fact, the sequence that used to leak a character into
    # a picture that never had them.
    at.session_state["chosen_characters"] = [ida_id]
    at.run()
    at = _button(at, "Draw it for a badge").click().run()

    assert not at.exception
    assert "Ida" not in captured["prompts"][0]


def test_the_badge_is_actually_58_mm_not_just_captioned_as_one() -> None:
    """The caption text ("a 58 mm badge") is a literal string, so nothing
    before this test checked that the geometry Doodle actually draws
    matches the number in it. Changing BADGE_58MM's diameters to 25 mm left
    every existing test green because none of them measured the picture.

    render_badge_preview sizes its page to the cut diameter plus a fixed
    4 mm margin on each side plus a 0.1 mm fit allowance, then rasters it at
    200 dpi (app.py's default): a real, independent check on the number
    baked into the preview's own pixels.
    """

    at = _result_screen()
    preview = next(iter(at.session_state["badge_previews"].values()))
    image = Image.open(BytesIO(preview))

    promised_mm = 58.0
    page_mm = promised_mm + (2 * 4.0) + 0.1
    expected_px = round(page_mm / 25.4 * 200)
    assert abs(image.width - expected_px) <= 1, (
        f"expected roughly {expected_px}px for a {promised_mm} mm badge, got {image.width}px"
    )


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


def test_going_back_moves_the_picture_and_its_badge() -> None:
    """ "Go back to this" must move the picture on screen, and the badge with it.

    The button set current_version and called _set_current_artwork but never
    _prepare_quick_outputs, so quick_processed (what the result screen and the
    badge strip both read) stayed on the version the user had just left: the
    picture on screen looked untouched by the click.
    """

    original = GeneratedArtwork(
        image_bytes=ARTWORK, prompt="original", provider="OpenAI", model="gpt-image-2"
    )
    changed = GeneratedArtwork(
        image_bytes=NEW_ARTWORK,
        prompt="changed",
        provider="OpenAI",
        model="gpt-image-2",
    )
    chain = history.append(history.start(original), changed, "give it a hat", parent=0)

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = NEW_ARTWORK
    at.session_state["quick_processed"] = NEW_ARTWORK
    at.session_state["quick_pdf"] = PDF
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {
        "source": "test",
        "concept": "Blue dinosaur",
    }
    at.session_state["doodle_versions"] = chain
    at.session_state["current_version"] = 1
    at.run()

    at = _button(at, "Go back to this").click().run()

    assert not at.exception
    assert at.session_state["current_version"] == 0
    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["quick_processed"] is not None
    assert at.session_state["quick_processed"] != NEW_ARTWORK
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


def _emitted_html(at: AppTest) -> str:
    return " ".join(str(element.proto.body) for element in at.get("html"))


def test_printing_your_badges_emits_a_genuine_a4_badge_sheet() -> None:
    """FB-11: the strip previewed a badge and could charge a generation to
    compose one, but the only controls on the screen ("Print this doodle",
    "Download the PDF") produced the A4 full page, never an actual badge.

    Driven against the real exporter (create_circle_sheet_pdf is not
    byte-stable between two calls with identical arguments, confirmed
    separately, so this checks structure rather than an exact byte match):
    a genuine PDF, distinct from the A4 full-page fixture, sized as an A4
    sheet rather than the ~66 mm square the free single-badge preview uses."""

    import base64
    import re

    import fitz

    at = _result_screen()
    assert "doodle-print-frame" not in _emitted_html(at)

    at = _button(at, "Print your badges").click().run()

    assert not at.exception
    emitted = _emitted_html(at)
    assert "doodle-print-frame" in emitted

    match = re.search(r'atob\("([A-Za-z0-9+/=]+)"\)', emitted)
    assert match, "no base64 PDF payload found in the print trigger"
    decoded = base64.b64decode(match.group(1))
    assert decoded.startswith(b"%PDF")
    # Not the same output as the A4 full-page print: a badge sheet must be
    # its own, different PDF, not the same button under a new label.
    assert decoded != PDF

    document = fitz.open(stream=decoded, filetype="pdf")
    assert document.page_count == 1
    page_rect = document[0].rect
    # A4 is 595 x 842 pt; the free preview's own single-badge page is a ~66
    # mm square (~187 pt). Only a genuine sheet is this large.
    assert page_rect.width > 500
    assert page_rect.height > 700


def test_the_badge_sheet_is_downloadable_too() -> None:
    at = _result_screen()
    labels_and_keys = [(button.label, button.key) for button in at.download_button]
    assert ("Download the PDF", "download_pdf_badges") in labels_and_keys
