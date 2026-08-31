"""Dragging a picture onto the page, from the drop well through to the model.

The browser half of this feature cannot be tested here: AppTest has no DOM, so
the injected script that catches the drag and hands the file to the well is
covered by tests/test_browser_drop.py as a pure string, and by a Chrome
DevTools run recorded in the design spec. What these tests own is everything
from the well inwards — that a file landing in it is prepared, described once,
carried to the provider as a reference, and cleared when it should be.

Setting the uploader's value directly is exactly what the injected script does
to it in a real browser: assign the file, fire a change event, let Streamlit
rerun. So this drives the same code path a real drop does, minus the drag.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from colouring_factory import appearance, characters, generators, timings
from colouring_factory.characters import save_character
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import load_settings, save_settings
from colouring_factory.prompts import DROPPED_PICTURE_RULE
from tests.test_photos import GPS_IFD_POINTER, _photo_with_gps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()

DRAFT_APPEARANCE = "A knitted rabbit with one ear turned down."


def _photo(colour: tuple[int, int, int] = (180, 90, 40)) -> bytes:
    """A real, Pillow-openable stand-in rather than a PNG signature.

    prepare_photo opens, transposes and re-encodes whatever reaches it, so a
    fake with only the right magic bytes fails inside it rather than
    exercising the path a real dropped photo takes.
    """

    buffer = BytesIO()
    Image.new("RGB", (24, 24), colour).save(buffer, format="PNG")
    return buffer.getvalue()


PHOTO = _photo()
OTHER_PHOTO = _photo((20, 120, 200))


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # Dropping a picture fires one describe_appearance call of its own. Patched
    # to a fixed answer by default so a test that does not care about the
    # description still makes no network call; a test about the call itself
    # overrides this.
    monkeypatch.setattr(
        appearance, "describe_appearance", lambda *a, **k: DRAFT_APPEARANCE
    )


def _homepage() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def _drop(at: AppTest, raw: bytes = PHOTO, name: str = "rabbit.png") -> AppTest:
    """Put a file in the well, the way the injected script does in a browser."""

    at.get("file_uploader")[0].set_value((name, raw, "image/png"))
    return at.run()


def _button(at: AppTest, label: str):
    for button in at.button:
        if button.label == label:
            return button
    raise AssertionError(
        f"no button labelled {label!r}: {[b.label for b in at.button]}"
    )


def _capture_refine(monkeypatch) -> dict:
    """Stand in for the paid call and keep what it was asked to draw."""

    seen: dict = {}

    def fake_refine(**kwargs):
        seen.update(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK,
            prompt=kwargs["prompt"],
            provider="OpenAI",
            model="gpt-image-2",
        )

    # Patched on colouring_factory.generators rather than on app: AppTest
    # re-executes app.py's whole module body, imports included, on every run,
    # so a patch on app.refine_with_provider is undone by the next interaction.
    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    return seen


# --- the well takes the picture ------------------------------------------


def test_the_homepage_carries_a_drop_well() -> None:
    """Without one the injected script finds no input and every drop lands on
    a page that cannot take it."""

    at = _homepage()
    assert at.get("file_uploader"), "the homepage has nowhere for a drop to go"


def test_a_dropped_picture_is_taken_into_the_session() -> None:
    at = _drop(_homepage())

    assert not at.exception
    assert at.session_state["dropped_picture"]
    assert at.session_state["dropped_picture_name"] == "rabbit.png"


def test_a_dropped_picture_is_stripped_of_its_metadata() -> None:
    """Every byte goes through prepare_photo, which is where the GPS in a
    phone photograph is removed. A second intake path that skipped it would
    quietly reintroduce the leak the upload tests exist to prevent."""

    at = _drop(_homepage(), _photo_with_gps(), "IMG_4021.jpg")

    stored = at.session_state["dropped_picture"]
    assert stored
    with Image.open(BytesIO(stored)) as reopened:
        assert dict(reopened.getexif()) == {}
        assert reopened.getexif().get_ifd(GPS_IFD_POINTER) == {}
    assert b"Apple" not in stored
    assert b"GPS" not in stored


def test_an_unreadable_drop_is_explained_rather_than_crashing() -> None:
    at = _drop(_homepage(), b"not a picture at all", "broken.png")

    assert not at.exception
    assert at.error
    assert not at.session_state["dropped_picture"]


def test_the_same_picture_is_only_taken_once(monkeypatch) -> None:
    """Streamlit reruns the whole script on every interaction and the well
    still holds the file, so without the hash guard this would buy another
    description on every keystroke."""

    calls: list[bytes] = []
    monkeypatch.setattr(
        appearance,
        "describe_appearance",
        lambda photo, **k: calls.append(photo) or DRAFT_APPEARANCE,
    )

    at = _drop(_homepage())
    assert len(calls) == 1

    at.text_input(key="home_prompt").set_value("riding a rocket").run()
    at.text_input(key="home_prompt").set_value("riding a rocket to the moon").run()

    assert len(calls) == 1, "an unrelated rerun bought a second description"


def test_a_different_picture_is_taken_again(monkeypatch) -> None:
    calls: list[bytes] = []
    monkeypatch.setattr(
        appearance,
        "describe_appearance",
        lambda photo, **k: calls.append(photo) or DRAFT_APPEARANCE,
    )

    at = _drop(_homepage())
    at = _drop(at, OTHER_PHOTO, "other.png")

    assert len(calls) == 2


def test_a_failed_description_does_not_block_the_drop(monkeypatch) -> None:
    """The picture is the point; the sentence is a bonus. Swallowed exactly as
    the characters screen swallows its own."""

    def refuses(*a, **k):
        raise GeneratorError("no", code="network")

    monkeypatch.setattr(appearance, "describe_appearance", refuses)

    at = _drop(_homepage())

    assert not at.exception
    assert at.session_state["dropped_picture"]
    assert at.session_state["dropped_picture_appearance"] == ""


# --- the prompt bar shows it -----------------------------------------------


def test_the_bar_shows_the_picture_and_asks_a_different_question() -> None:
    at = _drop(_homepage())

    assert at.get("image"), "the dropped picture is not shown in the bar"
    assert "with it" in at.text_input(key="home_prompt").placeholder


def test_removing_the_picture_actually_removes_it() -> None:
    """Clicked, not merely asserted present: a recovery control that raises
    when pressed looks identical to a working one until somebody presses it."""

    at = _drop(_homepage())
    assert at.session_state["dropped_picture"]

    _button(at, "Remove picture").click().run()

    assert not at.exception
    assert not at.session_state["dropped_picture"]
    assert not at.session_state["dropped_picture_appearance"]


def test_the_homepage_keeps_its_two_buttons_until_a_picture_arrives() -> None:
    """The interface rule is one full-width element and the button that acts
    on it. Remove picture may only exist when there is one to remove."""

    at = _homepage()
    assert [button.label for button in at.button] == ["Draw it", "Add a character"]

    at = _drop(at)
    assert "Remove picture" in [button.label for button in at.button]


# --- drawing with it -------------------------------------------------------


def test_a_picture_with_no_words_draws_from_the_picture(monkeypatch) -> None:
    """The homepage's own contract is that a blank box does nothing. A picture
    is an idea, so it has to be the one exception."""

    seen = _capture_refine(monkeypatch)

    at = _drop(_homepage())
    _button(at, "Draw it").click().run()

    assert not at.exception
    assert seen, "no drawing was requested"
    assert at.session_state["dropped_picture"] in seen["reference_images"]
    assert DROPPED_PICTURE_RULE in seen["prompt"]


def test_a_blank_box_with_no_picture_still_does_nothing() -> None:
    """The contract the exception above must not break."""

    at = _homepage()
    _button(at, "Draw it").click().run()

    assert at.session_state["screen"] == "home"


def test_the_description_becomes_the_idea_when_nothing_is_typed(monkeypatch) -> None:
    """The generating screen renders the idea as the largest words on the
    page, and the connection screen shows it on the idea-waiting card, so an
    empty one leaves a parent staring at a blank wait."""

    _capture_refine(monkeypatch)

    at = _drop(_homepage())
    _button(at, "Draw it").click().run()

    assert DRAFT_APPEARANCE in at.session_state["generation_idea"]


def test_a_picture_without_a_description_still_names_the_wait(monkeypatch) -> None:
    def refuses(*a, **k):
        raise GeneratorError("no", code="network")

    monkeypatch.setattr(appearance, "describe_appearance", refuses)
    _capture_refine(monkeypatch)

    at = _drop(_homepage())
    _button(at, "Draw it").click().run()

    assert at.session_state["generation_idea"] == "the picture you dropped"


def test_words_and_a_picture_reach_the_model_together(monkeypatch) -> None:
    seen = _capture_refine(monkeypatch)

    at = _drop(_homepage())
    at.text_input(key="home_prompt").set_value("riding a rocket to the moon").run()
    _button(at, "Draw it").click().run()

    assert not at.exception
    assert "riding a rocket to the moon" in seen["prompt"]
    assert DROPPED_PICTURE_RULE in seen["prompt"]
    assert at.session_state["dropped_picture"] in seen["reference_images"]


def test_a_dropped_picture_is_attached_after_the_cast(monkeypatch) -> None:
    """The ordinal words in the prompt are the only thing binding a picture to
    what it shows, so the attachment order and the introduction order have to
    agree."""

    seen = _capture_refine(monkeypatch)
    save_character(photo=PHOTO, portrait=ARTWORK, name="Ida", kind="person", marks="")

    at = _homepage()
    ida = characters.list_characters()[0].id
    at.session_state["chosen_characters"] = [ida]
    at.run()
    at = _drop(at)
    _button(at, "Draw it").click().run()

    assert not at.exception
    references = seen["reference_images"]
    assert len(references) == 2
    assert references[-1] == at.session_state["dropped_picture"]
    assert "The first picture is Doodle's drawing of Ida" in seen["prompt"]
    assert "The second picture is one the reader dropped" in seen["prompt"]


def test_a_drawing_with_a_dropped_picture_is_timed_as_one(monkeypatch) -> None:
    """A drawing carrying a picture is slower than one drawn from words, and
    the waiting screen's own estimate is trained on that split. Filing this
    one under words would teach the wrong distribution to the very screen the
    parent watches while waiting."""

    _capture_refine(monkeypatch)
    recorded: list[str] = []
    real_key = timings.settings_key

    def spy(**kwargs):
        recorded.append(bool(kwargs["with_references"]))
        return real_key(**kwargs)

    monkeypatch.setattr(timings, "settings_key", spy)

    at = _drop(_homepage())
    _button(at, "Draw it").click().run()

    assert not at.exception
    assert recorded == [True], "the drawing was filed as if it came from words"


def test_starting_a_new_doodle_forgets_the_picture(monkeypatch) -> None:
    """A cast survives a new doodle because it answers "who am I drawing
    for". One picture does not, and leaving it attached would put it into the
    next unrelated drawing and charge for it again."""

    _capture_refine(monkeypatch)

    at = _drop(_homepage())
    _button(at, "Draw it").click().run()
    _button(at, "New doodle").click().run()

    assert not at.exception
    assert not at.session_state["dropped_picture"]
    assert at.session_state["screen"] == "home"


# --- what the picture costs -----------------------------------------------


def test_a_dropped_picture_reserves_a_reference_slot() -> None:
    """A dropped picture occupies one of the service's reference places. A
    parent who fills every place with characters and then drops a picture has
    built a batch that cannot succeed, and the interface never renders a
    control that can only fail."""

    at = _homepage()
    save_character(photo=PHOTO, portrait=ARTWORK, name="Ida", kind="person", marks="")
    at.session_state["chosen_characters"] = [characters.list_characters()[0].id]
    at.run()

    before = " ".join(str(caption.value) for caption in at.caption)
    assert "looks at up to 16 at once" in before
    assert "takes one of its places" not in before

    at = _drop(at)

    after = " ".join(str(caption.value) for caption in at.caption)
    assert "looks at up to 15 at once" in after
    assert "The picture you dropped takes one of its places." in after


def test_a_service_that_cannot_see_pictures_says_so(monkeypatch) -> None:
    """Recraft draws from no reference at all. The injected script is blind to
    which service is connected on purpose — a payload that varied by provider
    would be re-inserted on every rerun — so Python is what refuses, and it
    names the control that fixes it."""

    monkeypatch.setenv("RECRAFT_API_TOKEN", "rc-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    at = _homepage()
    save_settings({**load_settings(), "image_provider": "recraft"})
    at.run()
    at = _drop(at)

    assert not at.exception
    assert not at.session_state["dropped_picture"]
    assert at.session_state["home_error_code"] == "no_reference_support"


def test_the_picture_is_held_before_the_service_is_asked_about_it(monkeypatch) -> None:
    """Asking what is in a photograph takes a second or two. Doing it in the
    same run as the drop holds the whole page still while a parent waits for
    the thumbnail they just dropped to appear at all, so the picture is stored
    and painted first and the asking happens on the run after."""

    seen_state: list[bool] = []

    def describe(photo, **kwargs):
        import streamlit as st

        seen_state.append(bool(st.session_state.get("dropped_picture")))
        return DRAFT_APPEARANCE

    monkeypatch.setattr(appearance, "describe_appearance", describe)

    at = _drop(_homepage())

    assert seen_state == [True], (
        "the description was bought before the picture was stored, so the "
        "thumbnail could not have been on screen yet"
    )
    assert at.session_state["dropped_picture_appearance"] == DRAFT_APPEARANCE
    assert at.session_state["dropped_picture_described"] is True


def test_the_service_is_asked_about_a_picture_only_once(monkeypatch) -> None:
    """The flag, not the presence of a description, is what stops a second
    call: a service that answered with an empty string would otherwise be
    asked again on every rerun for the life of the picture."""

    calls: list[int] = []
    monkeypatch.setattr(
        appearance,
        "describe_appearance",
        lambda *a, **k: calls.append(1) or "",
    )

    at = _drop(_homepage())
    assert at.session_state["dropped_picture_appearance"] == ""
    assert len(calls) == 1

    at.text_input(key="home_prompt").set_value("a rocket").run()
    at.text_input(key="home_prompt").set_value("a rocket ship").run()

    assert len(calls) == 1, "an empty answer was treated as no answer at all"
