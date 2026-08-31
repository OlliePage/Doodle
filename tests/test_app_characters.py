"""The characters screen: adding a face to the cast is the caricature feature.

Drawing a character's portrait and drawing a scene are one mechanism with two
doors, so these fixtures (PHOTO_BYTES, the isolation fixture, the screen
builder, _save_two_characters) are written here even where this file's own
tests do not use all of them, ready for whatever else joins the cast.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from colouring_factory import appearance, generators
from colouring_factory.characters import (
    characters_root,
    delete_character,
    list_characters,
    load_character,
    load_character_image,
    save_character,
)
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import load_settings, save_settings

# The default a photo's description resolves to unless a test overrides it.
# Distinct enough from any test's own hand-typed marks that a test asserting
# on this exact text cannot be satisfied by marks leaking into the wrong
# field by accident.
DRAFT_APPEARANCE = "Brown eyes, wavy dark-brown hair, light-brown skin."

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()
OTHER_ARTWORK = (PROJECT_ROOT / "assets" / "demo_robot_balloons.png").read_bytes()


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
    # Choosing a photograph fires one describe_appearance call of its own,
    # separate from the portrait drawing every test here already fakes —
    # patched to a fixed answer by default so a test that does not care
    # about appearance still makes no network call. A test about the call
    # itself overrides this with its own monkeypatch.
    monkeypatch.setattr(
        appearance, "describe_appearance", lambda *a, **k: DRAFT_APPEARANCE
    )


def _characters_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.run()
    return at


# The picker's trigger is a face icon rather than a word, so it is found by
# that icon and its label carries only the count. Matching on the label alone
# would find the wrong control the moment another popover renders empty.
PICKER_ICON = ":material/face:"


def _picker(at, required: bool = True):
    for popover in at.get("popover"):
        if popover.proto.popover.icon == PICKER_ICON:
            return popover
    if required:
        raise AssertionError("the characters picker is not on the page")
    return None


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
    # Adding someone to the cast is its own action, not a doodle in disguise:
    # it stays on this screen, with a confirmation naming who was added.
    assert at.session_state["screen"] == "characters"
    assert at.session_state["quick_processed"] is None
    confirmations = " ".join(str(s.value) for s in at.success)
    assert "ida" in confirmations.lower()
    assert "characters" in confirmations.lower()


def test_choosing_a_photo_drafts_an_appearance_from_it(monkeypatch) -> None:
    """The bug this whole feature exists for: colour lives only in the
    photograph, and is gone forever once a black-and-white drawing exists.
    A description has to be drafted as soon as the photo is chosen, before
    the parent has typed anything else, so there is something to correct
    rather than nothing to build from."""

    calls = []

    def fake_describe(photo, *, provider_id, api_key):
        calls.append(photo)
        return DRAFT_APPEARANCE

    monkeypatch.setattr(appearance, "describe_appearance", fake_describe)

    at = _characters_screen()
    at = (
        at.get("file_uploader")[0]
        .set_value(("ida.png", PHOTO_BYTES, "image/png"))
        .run()
    )

    assert not at.exception
    assert len(calls) == 1
    assert at.text_area(key="character_appearance").value == DRAFT_APPEARANCE


def test_the_draft_is_not_refetched_on_every_unrelated_rerun(monkeypatch) -> None:
    """Every widget interaction reruns the whole script. Refetching on each
    one would mean a paid text call for every keystroke typed into the name
    box after a photo is already chosen."""

    calls = []
    monkeypatch.setattr(
        appearance,
        "describe_appearance",
        lambda *a, **k: calls.append(1) or DRAFT_APPEARANCE,
    )

    at = _characters_screen()
    at = (
        at.get("file_uploader")[0]
        .set_value(("ida.png", PHOTO_BYTES, "image/png"))
        .run()
    )
    at = at.text_input(key="character_name").set_value("Ida").run()
    at = at.text_area(key="character_marks").set_value("Curly hair.").run()

    assert len(calls) == 1


def test_the_parent_can_correct_the_drafted_appearance_before_saving(
    monkeypatch,
) -> None:
    """A model's guess about a child's colouring must be as correctable as
    every other word on this form, before it is ever saved."""

    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at = (
        at.get("file_uploader")[0]
        .set_value(("ida.png", PHOTO_BYTES, "image/png"))
        .run()
    )
    at.text_input(key="character_name").set_value("Ida").run()
    at.text_area(key="character_appearance").set_value(
        "Brown eyes, dark hair, light-brown skin."
    ).run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    saved = list_characters()[0]
    assert saved.appearance == "Brown eyes, dark hair, light-brown skin."


def test_the_drafted_appearance_is_saved_with_the_character(monkeypatch) -> None:
    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at = (
        at.get("file_uploader")[0]
        .set_value(("ida.png", PHOTO_BYTES, "image/png"))
        .run()
    )
    at.text_input(key="character_name").set_value("Ida").run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    saved = list_characters()[0]
    assert saved.appearance == DRAFT_APPEARANCE


def test_a_failed_description_still_lets_the_character_be_saved(monkeypatch) -> None:
    """The drawing already spent one generation by the time this could fail:
    a photograph that cannot be described is not a reason to lose the
    portrait and the name too."""

    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    def failing_describe(*a, **k):
        raise GeneratorError(
            "OpenAI could not describe the photograph.", code="network"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    monkeypatch.setattr(appearance, "describe_appearance", failing_describe)

    at = _characters_screen()
    at = (
        at.get("file_uploader")[0]
        .set_value(("ida.png", PHOTO_BYTES, "image/png"))
        .run()
    )
    at.text_input(key="character_name").set_value("Ida").run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    saved = list_characters()[0]
    assert saved.name == "Ida"
    assert saved.appearance == ""


def test_drawing_the_idea_again_after_opening_a_portrait_does_not_trap_on_connect(
    monkeypatch,
) -> None:
    """FB-01: the result screen's leftmost button, "Draw this idea again",
    always reads generation_idea. A portrait opened as a doodle has no scene
    idea behind it, so if that route ever left the key unset the button
    would raise missing_prompt — which _render_generating_screen then
    misrouted to the Connect screen: a screen that simultaneously said
    OpenAI was already connected and that a description was needed, with
    two of its three buttons looping back to themselves and Back escaping
    to Doodle Studio. Opening a portrait as a doodle must carry an idea
    forward the same way the portrait-drawing path this regression was
    first written for did."""

    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    def fake_generate(**kwargs):
        return [
            GeneratedArtwork(
                image_bytes=OTHER_ARTWORK,
                prompt=kwargs["prompts"][0],
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()

    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert at.session_state["screen"] == "characters"
    ida_id = list_characters()[0].id

    for button in at.button:
        if button.key == f"open_as_doodle_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Open as a doodle button not found")

    assert at.session_state["screen"] == "result"
    assert str(at.session_state["generation_idea"]).strip(), (
        "no idea was carried forward from the opened portrait"
    )

    for button in at.button:
        if button.label == "Draw this idea again":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw this idea again button not found")

    assert not at.exception
    assert at.session_state["screen"] != "connect", (
        f"trapped on the connect screen: {at.session_state['connection_error']}"
    )


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


def test_the_back_button_returns_to_the_homepage() -> None:
    """The homepage's "Add a character" button is the only route to this screen,
    so Back has exactly one place to return to. An earlier version tracked
    a characters_return key that was only ever set to "home", making the
    branch that read it unreachable and covered only by a test that set
    state no production path ever set."""

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.run()

    for button in at.button:
        if button.label == "Back":
            button.click().run()
            break
    else:
        raise AssertionError("Back button not found")

    assert not at.exception
    assert at.session_state["screen"] == "home"


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


def test_editing_a_characters_words_persists_with_no_redraw(monkeypatch) -> None:
    """FB-05: the only control on a saved character used to be Delete, which
    also destroys the photograph, so fixing a typo cost a fresh upload and a
    paid drawing. Save changes must correct the name, the kind and the
    marks sentence the design calls the repair, without spending a
    generation."""

    def fail_if_called(**kwargs):
        raise AssertionError("editing the words must not draw anything")

    monkeypatch.setattr(generators, "refine_with_provider", fail_if_called)
    ida_id = save_character(
        photo=PHOTO_BYTES,
        portrait=ARTWORK,
        name="Ida",
        kind="person",
        marks="Old marks.",
    )

    at = _characters_screen()
    at.text_input(key=f"edit_name_{ida_id}").set_value("Ida-Rose").run()
    at.segmented_control(key=f"edit_kind_{ida_id}").set_value("A toy").run()
    at.text_area(key=f"edit_marks_{ida_id}").set_value("A missing button eye.").run()

    for button in at.button:
        if button.key == f"save_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Save changes button not found")

    assert not at.exception
    saved = load_character(ida_id)
    assert saved.name == "Ida-Rose"
    assert saved.kind == "toy"
    assert saved.marks == "A missing button eye."
    # The photograph and the portrait are untouched by an edit of the words.
    assert load_character_image(ida_id, portrait=False) == PHOTO_BYTES
    assert load_character_image(ida_id) == ARTWORK


def test_editing_a_characters_appearance_persists_with_no_redraw(monkeypatch) -> None:
    """A model's guess about a child's colouring must be as correctable as
    the name, kind or marks beside it — the exact repair the bug this
    feature exists for needs."""

    def fail_if_called(**kwargs):
        raise AssertionError("editing the words must not draw anything")

    monkeypatch.setattr(generators, "refine_with_provider", fail_if_called)
    ida_id = save_character(
        photo=PHOTO_BYTES,
        portrait=ARTWORK,
        name="Ida",
        kind="person",
        marks="",
        appearance="Blonde hair, blue eyes, pale skin.",
    )

    at = _characters_screen()
    at.text_area(key=f"edit_appearance_{ida_id}").set_value(
        "Brown hair, brown eyes, light-brown skin."
    ).run()

    for button in at.button:
        if button.key == f"save_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Save changes button not found")

    assert not at.exception
    assert (
        load_character(ida_id).appearance == "Brown hair, brown eyes, light-brown skin."
    )


def test_an_existing_character_can_be_described_from_their_stored_photo(
    monkeypatch,
) -> None:
    """A character saved before this feature existed has no appearance, and
    the redraw path already loads their stored photograph — proof that the
    same material is here to fill it in without asking for a fresh upload."""

    captured = {}

    def fake_describe(photo, *, provider_id, api_key):
        captured["photo"] = photo
        return DRAFT_APPEARANCE

    monkeypatch.setattr(appearance, "describe_appearance", fake_describe)
    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _characters_screen()
    for button in at.button:
        if button.key == f"describe_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Fill in from their photo button not found")

    assert not at.exception
    assert captured["photo"] == PHOTO_BYTES
    assert load_character(ida_id).appearance == DRAFT_APPEARANCE


def test_the_fill_in_button_is_not_offered_once_a_character_has_a_description() -> None:
    ida_id = save_character(
        photo=PHOTO_BYTES,
        portrait=ARTWORK,
        name="Ida",
        kind="person",
        marks="",
        appearance="Brown hair, brown eyes, light-brown skin.",
    )

    at = _characters_screen()
    assert not any(button.key == f"describe_character_{ida_id}" for button in at.button)


def test_a_failed_description_leaves_the_button_pressable_again(monkeypatch) -> None:
    def failing_describe(*a, **k):
        raise GeneratorError(
            "OpenAI could not describe the photograph.", code="network"
        )

    monkeypatch.setattr(appearance, "describe_appearance", failing_describe)
    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _characters_screen()
    for button in at.button:
        if button.key == f"describe_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Fill in from their photo button not found")

    assert not at.exception
    assert load_character(ida_id).appearance == ""
    redo = next(
        button for button in at.button if button.key == f"describe_character_{ida_id}"
    )
    assert redo.disabled is False


def test_editing_a_character_rejects_a_blank_name() -> None:
    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _characters_screen()
    at.text_input(key=f"edit_name_{ida_id}").set_value("   ").run()

    for button in at.button:
        if button.key == f"save_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Save changes button not found")

    assert not at.exception
    assert load_character(ida_id).name == "Ida"
    errors = " ".join(str(e.value) for e in at.error)
    assert "name" in errors.lower()


def test_redrawing_a_portrait_uses_the_stored_photo_with_no_new_upload(
    monkeypatch,
) -> None:
    """FB-05: the redraw must use the photograph already saved on disk — no
    file_uploader is offered here — and must replace only that one
    character's portrait rather than creating a second character."""

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=OTHER_ARTWORK,
            prompt="p",
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id = save_character(
        photo=PHOTO_BYTES,
        portrait=ARTWORK,
        name="Ida",
        kind="person",
        marks="Curly hair.",
    )

    at = _characters_screen()
    for button in at.button:
        if button.key == f"redraw_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Redraw their portrait button not found")

    assert not at.exception
    assert captured["reference_images"] == (PHOTO_BYTES,)
    assert "Ida" in captured["prompt"]
    assert [c.id for c in list_characters()] == [ida_id], (
        "a redraw must not create a second character"
    )
    assert load_character_image(ida_id) == OTHER_ARTWORK
    assert load_character_image(ida_id, portrait=False) == PHOTO_BYTES
    # A redraw is a repair to the cast, like "Save changes" beside it, not a
    # doodle: it stays here, with a confirmation naming who was redrawn.
    assert at.session_state["screen"] == "characters"
    confirmations = " ".join(str(s.value) for s in at.success)
    assert "ida" in confirmations.lower()


def test_a_click_while_draw_them_is_already_in_flight_draws_nothing_more(
    monkeypatch,
) -> None:
    """Streamlit can queue a click made while a control's own previous press
    is still blocked in the drawing service's call, and replay it the
    instant that call returns — which bought a real parent six identical
    characters called Aria from what he experienced as one press each. The
    busy flag must stop the replay before it ever reaches the drawing
    service, not merely explain the picture afterwards."""

    calls = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    # Stands in for the second, queued click: its own previous press has not
    # returned yet, so the flag it set is still true when this one lands.
    at.session_state["busy_add_character"] = True

    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert calls == [], "a click arriving while one is in flight must draw nothing"
    assert list_characters() == []


def test_draw_them_is_pressable_again_once_its_own_drawing_finishes(
    monkeypatch,
) -> None:
    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert at.session_state["busy_add_character"] is False


def test_a_failed_draw_them_leaves_the_control_pressable_again(monkeypatch) -> None:
    """A guard that never lets go of its flag on a failure would wedge the
    button shut for the rest of the session — a worse bug than the one it
    fixes."""

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
    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert at.session_state["busy_add_character"] is False
    assert list_characters() == []


def test_draw_them_shows_progress_while_it_draws(monkeypatch) -> None:
    """Pressed with no feedback, this button looked broken and got pressed
    again — the defect the busy-flag tests above guard the wallet against.
    This checks the other half: something on screen actually says a
    drawing is under way, named for who it is drawing, before the paid call
    is made — not only that the call eventually happens."""

    import streamlit

    spinner_texts: list[str] = []

    class _RecordingSpinner:
        def __init__(self, text: str = "") -> None:
            spinner_texts.append(text)

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> bool:
            return False

    monkeypatch.setattr(streamlit, "spinner", _RecordingSpinner)

    def fake_refine(**kwargs):
        assert any("ida" in text.lower() for text in spinner_texts), (
            "no progress naming Ida was shown before the drawing call"
        )
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert spinner_texts, "Draw them must show progress while it draws"


def test_a_click_while_a_redraw_is_already_in_flight_draws_nothing_more(
    monkeypatch,
) -> None:
    calls = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        return GeneratedArtwork(
            image_bytes=OTHER_ARTWORK,
            prompt="p",
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _characters_screen()
    at.session_state[f"busy_redraw_{ida_id}"] = True
    for button in at.button:
        if button.key == f"redraw_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Redraw their portrait button not found")

    assert not at.exception
    assert calls == []
    assert load_character_image(ida_id) == ARTWORK, "the old portrait must be untouched"


def test_a_failed_redraw_leaves_the_control_pressable_again(monkeypatch) -> None:
    def refuse(**kwargs):
        raise GeneratorError(
            "OpenAI would not draw from that picture.",
            provider="OpenAI",
            code="photo_declined",
        )

    monkeypatch.setattr(generators, "refine_with_provider", refuse)
    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _characters_screen()
    for button in at.button:
        if button.key == f"redraw_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Redraw their portrait button not found")

    assert not at.exception
    assert at.session_state[f"busy_redraw_{ida_id}"] is False
    assert load_character_image(ida_id) == ARTWORK


def test_redraw_shows_progress_while_it_draws(monkeypatch) -> None:
    import streamlit

    spinner_texts: list[str] = []

    class _RecordingSpinner:
        def __init__(self, text: str = "") -> None:
            spinner_texts.append(text)

        def __enter__(self):
            return self

        def __exit__(self, *_exc) -> bool:
            return False

    monkeypatch.setattr(streamlit, "spinner", _RecordingSpinner)

    def fake_refine(**kwargs):
        assert any("ida" in text.lower() for text in spinner_texts), (
            "no progress naming Ida was shown before the redraw call"
        )
        return GeneratedArtwork(
            image_bytes=OTHER_ARTWORK,
            prompt="p",
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    at = _characters_screen()
    for button in at.button:
        if button.key == f"redraw_character_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Redraw their portrait button not found")

    assert not at.exception
    assert spinner_texts, "Redraw their portrait must show progress while it draws"


def test_saving_a_character_whose_name_already_exists_is_noted(monkeypatch) -> None:
    """Six identical characters from one accident is a real defect; two
    deliberate ones sharing a name is allowed by design. The difference is
    telling the parent, not blocking the save or asking them to confirm."""

    save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Aria", kind="person", marks=""
    )

    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=OTHER_ARTWORK,
            prompt="p",
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("aria2.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Aria").run()
    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert [c.name for c in list_characters()].count("Aria") == 2
    notices = " ".join(str(i.value) for i in at.info)
    assert "aria" in notices.lower()
    assert "already" in notices.lower()


def test_a_character_with_a_new_name_gets_no_duplicate_note(monkeypatch) -> None:
    def fake_refine(**kwargs):
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    for button in at.button:
        if button.label == "Draw them":
            at = button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert not at.info, [str(i.value) for i in at.info]


def test_a_saved_characters_portrait_can_be_opened_as_a_doodle() -> None:
    """Every tile, not only a freshly-drawn one, gets a deliberate route to
    the result screen with printing, the badge strip and the colour preview
    — the other half of what a picture of a photograph is for, now that
    adding someone to the cast no longer doubles as that route."""

    ida_id, _bo_id = _save_two_characters()

    at = _characters_screen()
    for button in at.button:
        if button.key == f"open_as_doodle_{ida_id}":
            at = button.click().run()
            break
    else:
        raise AssertionError("Open as a doodle button not found")

    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["quick_processed"]
    assert at.session_state["current_metadata"]["generation"]["characters"] == [ida_id]
    assert str(at.session_state["generation_idea"]).strip()


def test_starting_a_new_doodle_keeps_the_chosen_cast() -> None:
    """A parent drawing for the same children wants the same cast next time,
    the same reasoning the homepage settings already follow."""

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.session_state["chosen_characters"] = ["someone"]
    at.run()

    for button in at.button:
        if button.label == "New doodle":
            button.click().run()
            break
    else:
        raise AssertionError("New doodle button not found")

    assert at.session_state["screen"] == "home"
    assert at.session_state["chosen_characters"] == ["someone"]


def test_a_ticked_character_survives_going_to_the_add_screen_and_back() -> None:
    """Per-id widget keys are destroyed the moment they are not rendered.

    Proved on 2026-08-30: tick a character, navigate away, come back, and the
    key reads False. setdefault does not help, because the key is deleted
    after the run in which the widget is absent.
    """

    ida_id, _bo_id = _save_two_characters()
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    at.checkbox(key=f"character_pick_{ida_id}").set_value(True).run()
    at.session_state["screen"] = "characters"
    at.run()
    at.session_state["screen"] = "home"
    at.run()

    assert at.session_state["chosen_characters"] == [ida_id]
    assert at.checkbox(key=f"character_pick_{ida_id}").value is True


def test_the_picker_label_is_a_count_never_a_list_of_names() -> None:
    """A joined list of names is unbounded and would push the settings line
    sideways on a phone, whose CSS gives it no way to wrap or shrink."""

    ida_id, bo_id = _save_two_characters()
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    picker = _picker(at)
    assert picker.proto.popover.label == ""

    at.checkbox(key=f"character_pick_{ida_id}").set_value(True).run()
    assert _picker(at).proto.popover.label == "1"
    labels = [popover.proto.popover.label for popover in at.get("popover")]
    assert "Ida" not in " ".join(labels)

    at.checkbox(key=f"character_pick_{bo_id}").set_value(True).run()
    popover_labels = [popover.proto.popover.label for popover in at.get("popover")]
    assert _picker(at).proto.popover.label == "2"


def test_two_characters_sharing_a_name_can_both_be_ticked_independently() -> None:
    """app.py:922 used to key each tick box by the character's *name*, so a
    girl called Ida and her teddy also called Ida collided in a duplicate
    Streamlit widget key. That raised inside the settings line, so the
    homepage rendered nothing below it, with no recovery short of deleting a
    folder from the data directory by hand. Keying by id fixes it."""

    ida_person_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )
    ida_teddy_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="toy", marks=""
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception

    at.checkbox(key=f"character_pick_{ida_person_id}").set_value(True).run()
    assert not at.exception
    assert at.session_state["chosen_characters"] == [ida_person_id]
    assert at.checkbox(key=f"character_pick_{ida_teddy_id}").value is False

    at.checkbox(key=f"character_pick_{ida_teddy_id}").set_value(True).run()
    assert not at.exception
    assert set(at.session_state["chosen_characters"]) == {
        ida_person_id,
        ida_teddy_id,
    }


def test_two_characters_sharing_a_name_are_both_named_when_drawing(
    monkeypatch,
) -> None:
    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_person_id = save_character(
        photo=PHOTO_BYTES,
        portrait=ARTWORK,
        name="Ida",
        kind="person",
        marks="Curly hair.",
    )
    ida_teddy_id = save_character(
        photo=PHOTO_BYTES,
        portrait=ARTWORK,
        name="Ida",
        kind="toy",
        marks="A missing button eye.",
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_person_id, ida_teddy_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "having a tea party"
    at.run()

    assert not at.exception
    assert len(captured["reference_images"]) == 2
    assert captured["prompt"].count("Ida") == 2


def test_deleting_a_character_clears_their_tick() -> None:
    """app.py:1201-1204 filtered chosen_characters against character ids
    while the selection stored names, so the filter was a no-op: delete
    someone, save a different character with the same name later, and they
    came back silently pre-ticked. Storing ids throughout is what makes this
    filter actually work."""

    ida_id, bo_id = _save_two_characters()

    at = _characters_screen()
    at.session_state["chosen_characters"] = [ida_id, bo_id]
    at.run()

    for button in at.button:
        if button.key == f"delete_character_{ida_id}":
            button.click().run()
            break
    else:
        raise AssertionError("Delete button for Ida not found")
    for button in at.button:
        if button.key == f"confirm_delete_character_{ida_id}":
            button.click().run()
            break
    else:
        raise AssertionError("Confirm delete button for Ida not found")

    assert not at.exception
    assert at.session_state["chosen_characters"] == [bo_id]


def test_the_picker_carries_no_more_weight_than_its_siblings_on_the_line() -> None:
    """The other three controls on the settings line pass type="tertiary" so
    the row reads as plain grey text; this one must match or it will sit as
    a visibly heavier, bordered pill against the rest of the line."""

    _save_two_characters()
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    assert _picker(at).proto.popover.type == "tertiary"


def test_the_picker_is_offered_even_with_no_characters_saved() -> None:
    """Unlike Saved doodles (n) in the corner, this control must not wait
    until it has something to show: hiding it behind `if cast:` (app.py:906)
    left no route anywhere on a clean install that reached the characters
    screen, so a parent could never add their first character."""

    at = AppTest.from_file(APP, default_timeout=60)
    at.run()

    assert _picker(at) is not None


def test_the_characters_screen_is_reachable_from_a_totally_empty_homepage() -> None:
    """CRITICAL: a parent who has never used this feature must be able to
    find it. The whole popover, including "Add a character", used to be gated
    behind `if cast:`, so with nothing saved yet there was no control
    anywhere on the homepage that reached this screen at all."""

    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    assert list_characters() == []

    for button in at.button:
        if button.label == "Add a character":
            button.click().run()
            break
    else:
        raise AssertionError(
            "no route to the characters screen; saw buttons "
            f"{[b.label for b in at.button]}"
        )

    assert not at.exception
    assert at.session_state["screen"] == "characters"


def test_the_add_someone_button_opens_the_characters_screen() -> None:
    _save_two_characters()
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    for button in at.button:
        if button.label == "Add a character":
            button.click().run()
            break
    else:
        raise AssertionError("Add someone button not found")

    assert not at.exception
    assert at.session_state["screen"] == "characters"


def test_a_provider_with_no_reference_support_is_not_offered_the_picker() -> None:
    """The design says the control does not appear when a service declares
    it takes no reference pictures: Recraft's imageToImage endpoint cannot
    carry a cast at all, so ticking characters for it could never work."""

    _save_two_characters()
    save_settings({**load_settings(), "image_provider": "recraft"})

    at = AppTest.from_file(APP, default_timeout=60)
    at.run()

    assert not at.exception
    assert _picker(at, required=False) is None
    captions = " ".join(str(caption.value) for caption in at.caption)
    assert "recraft cannot draw from a picture" in captions.lower()


def test_a_provider_with_no_reference_support_is_not_offered_the_draw_button() -> None:
    """A Recraft user must not be shown "Draw them" and then told, on the
    characters screen, to go and change provider on the result screen."""

    save_settings({**load_settings(), "image_provider": "recraft"})

    at = _characters_screen()

    assert not at.exception
    assert not any(button.label == "Draw them" for button in at.button)
    captions = " ".join(str(caption.value) for caption in at.caption)
    assert "recraft cannot draw from a picture" in captions.lower()


def test_the_draw_button_names_its_cost() -> None:
    at = _characters_screen()

    for button in at.button:
        if button.label == "Draw them":
            assert "costs one generation" in str(button.help).lower()
            break
    else:
        raise AssertionError("Draw them button not found")


def test_a_chosen_character_is_sent_as_a_reference(monkeypatch) -> None:
    """The tick on the homepage must reach the drawing call: a reference
    picture attached, and the character's name in the prompt telling the
    model whose face the attached picture is."""

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    # monkeypatch.setattr on the app module is undone by the next widget
    # .run(), because AppTest re-executes the app's imports on every run.
    # Patching the source module survives every rerun.
    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id, _bo_id = _save_two_characters()

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "walking in a forest"
    at.run()

    assert not at.exception
    assert len(captured["reference_images"]) == 1
    assert "Ida" in captured["prompt"]
    assert "never as separate strands" in captured["prompt"]


def test_a_scene_is_drawn_from_the_photograph_not_the_caricature(monkeypatch) -> None:
    """FB-03: the stored portrait is a deliberate caricature — its own
    prompt says a "polite, accurate, flattering portrait is the wrong
    answer" — so sending it as the likeness reference for a scene draws
    every picture from that exaggeration rather than from the child or toy
    it was drawn from. The reference sent must be the photograph bytes,
    never the portrait bytes, and the two are deliberately different here so
    that sending the wrong one is something a test can catch rather than
    something that happens to still look right."""

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id, _bo_id = _save_two_characters()

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "walking in a forest"
    at.run()

    assert not at.exception
    assert captured["reference_images"] == (PHOTO_BYTES,)
    assert ARTWORK not in captured["reference_images"]


def test_a_deleted_characters_id_is_dropped_rather_than_crashing_the_draw(
    monkeypatch,
) -> None:
    """An id ticked before a character was deleted must not reach
    load_character_image, which would raise for a folder that is now gone."""

    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id, bo_id = _save_two_characters()
    delete_character(ida_id)

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_id, bo_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "walking in a forest"
    at.run()

    assert not at.exception
    assert len(captured["reference_images"]) == 1
    assert "Bo" in captured["prompt"]
    assert "Ida" not in captured["prompt"]


def test_pairing_with_a_chosen_cast_draws_both_sheets_with_the_characters_in_both(
    monkeypatch,
) -> None:
    """The grown-up pairing checkbox must not go silently ignored just
    because a character is chosen. The reviewer proved that combination drew
    one children's sheet, left the grown-up sheet's session keys empty and
    kept the box ticked with nothing said about it. Pairing is one scene at
    two detail levels, whether or not a cast is chosen, so the same reference
    portraits and the same idea go through refine_with_provider a second
    time, at grown-up detail."""

    calls = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        # Two distinguishable pictures, in call order, so the children's
        # sheet and the grown-up sheet can be told apart afterwards.
        image = ARTWORK if len(calls) == 1 else OTHER_ARTWORK
        return GeneratedArtwork(
            image_bytes=image,
            prompt=kwargs["prompt"],
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    ida_id, _bo_id = _save_two_characters()
    save_settings(
        {
            **load_settings(),
            "quick_pair_grown_up": True,
            "quick_age_profile": "2-3 years",
        }
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "building a sandcastle"
    at.run()

    assert not at.exception
    assert len(calls) == 2, "one sheet for them, one for the grown-up"
    assert all("Ida" in call["prompt"] for call in calls), (
        "the character must be in both readings of the scene, not just the first"
    )
    assert len(calls[0]["reference_images"]) == 1
    assert len(calls[1]["reference_images"]) == 1

    children_prompt, grown_up_prompt = calls[0]["prompt"], calls[1]["prompt"]
    assert "6 to 12 large colouring regions" in children_prompt
    assert "150 or more small colouring regions" in grown_up_prompt

    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["pair_raw"] == OTHER_ARTWORK
    assert at.session_state["pair_processed"] is not None
    assert at.session_state["pair_pdf"] is not None


def test_a_corrupted_portrait_does_not_take_down_the_whole_screen() -> None:
    """FB-02: st.image raising deep inside the render loop used to take the
    whole screen with it. Three characters, sorted alphabetically-reversed by
    save order below since list_characters returns newest first: the good
    one saved last must still render, and so must the add form beneath the
    loop, even though the corrupted one sorts between them."""

    save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="EarlyGood", kind="person", marks=""
    )
    zero_byte_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="ZeroByteMid", kind="person", marks=""
    )
    (characters_root() / zero_byte_id / "portrait.png").write_bytes(b"")
    save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="LateGood", kind="person", marks=""
    )

    at = _characters_screen()

    assert not at.exception
    names = " ".join(str(m.value) for m in at.markdown)
    assert "LateGood" in names
    assert "ZeroByteMid" in names
    assert "EarlyGood" in names
    assert any("could not be shown" in info.value.lower() for info in at.info)
    # The add form beneath the grid must still be reachable.
    assert any(button.label == "Draw them" for button in at.button)
    # The bad record's own delete button must still be on the page.
    assert any(button.key == f"delete_character_{zero_byte_id}" for button in at.button)


def test_a_non_image_portrait_file_also_degrades_rather_than_crashing() -> None:
    """Not just zero bytes: garbage bytes that pass no image-format check
    at all must degrade the same way."""

    garbage_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Garbage", kind="person", marks=""
    )
    (characters_root() / garbage_id / "portrait.png").write_bytes(
        b"this is not a png at all, just some bytes"
    )

    at = _characters_screen()

    assert not at.exception
    assert any("could not be shown" in info.value.lower() for info in at.info)
    assert any(button.key == f"delete_character_{garbage_id}" for button in at.button)


def _guidance_text(at: AppTest) -> str:
    return " ".join(
        str(element.value)
        for group in (at.error, at.markdown, at.caption)
        for element in group
    )


def test_a_declined_photo_while_drawing_a_scene_routes_home_not_to_connect(
    monkeypatch,
) -> None:
    """FB-07: photo_declined is about the picture, not the connection.

    Reachable only through a chosen cast (refine_with_provider, not
    generate_with_provider), this used to fall into the generating screen's
    default branch and land on the Connect screen, which has nothing to do
    with a declined photograph and nothing for the parent to fix there."""

    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )

    def refuse(**kwargs):
        raise GeneratorError(
            "OpenAI would not draw from that picture.",
            provider="OpenAI",
            code="photo_declined",
        )

    monkeypatch.setattr(generators, "refine_with_provider", refuse)

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "having a picnic"
    at.session_state["quick_mode"] = "ai"
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert not at.session_state["connection_error"]
    assert "picture" in _guidance_text(at).lower()


def test_too_many_characters_on_gemini_is_explained_not_silently_moved(
    monkeypatch,
) -> None:
    """FB-07: on Google Gemini specifically, the Connect screen only shows a
    connection_error whose recorded provider matches the radio's current
    selection. Before this fix, too_many_references landed there anyway and,
    because the radio still defaulted to OpenAI, the message was filtered
    out entirely: a parent moved with no explanation at all. Routing this
    code home instead means that filter is never reached."""

    ida_id, bo_id = _save_two_characters()
    save_settings({**load_settings(), "image_provider": "google"})
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")

    def refuse(**kwargs):
        raise GeneratorError(
            "Google Gemini can look at 1 picture at a time. Choose fewer characters.",
            provider="Google Gemini",
            code="too_many_references",
        )

    monkeypatch.setattr(generators, "refine_with_provider", refuse)

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = [ida_id, bo_id]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "at the park"
    at.session_state["quick_mode"] = "ai"
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert not at.session_state["connection_error"]
    guidance = _guidance_text(at).lower()
    assert "fewer characters" in guidance or "untick" in guidance


def test_the_picker_disables_further_ticks_once_the_provider_limit_is_reached(
    monkeypatch,
) -> None:
    """FB-07: the picker let a parent tick more characters than the
    connected service will accept, with no cap and no count shown. Google
    Gemini looks at 4 pictures at a time (colouring_factory/providers.py)."""

    ids = [
        save_character(
            photo=PHOTO_BYTES,
            portrait=ARTWORK,
            name=f"Character {i}",
            kind="person",
            marks="",
        )
        for i in range(5)
    ]
    save_settings({**load_settings(), "image_provider": "google"})
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    for character_id in ids[:4]:
        at.checkbox(key=f"character_pick_{character_id}").set_value(True).run()

    assert at.session_state["chosen_characters"] == ids[:4]
    # The fifth, unticked box must be disabled: ticking it would build a
    # request refine_with_provider can only reject with too_many_references.
    assert at.checkbox(key=f"character_pick_{ids[4]}").disabled is True
    # An already-ticked box stays enabled, so unticking back under the cap
    # is still possible.
    assert at.checkbox(key=f"character_pick_{ids[0]}").disabled is False
    popover_labels = [popover.proto.popover.label for popover in at.get("popover")]
    assert _picker(at).proto.popover.label == "4"


def test_the_picker_shows_a_distinct_portrait_for_each_character() -> None:
    """FB-12: name and a tick box only cannot tell two same-named characters
    apart. Save a girl called Ida and her teddy also called Ida — the exact
    collision _remember_chosen's own docstring names — and the picker must
    show two different pictures, not two identical rows."""

    ida_person_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )
    ida_teddy_id = save_character(
        photo=PHOTO_BYTES, portrait=OTHER_ARTWORK, name="Ida", kind="toy", marks=""
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    # Not just "a popover with a checkbox": the grown-up-detail popover has
    # one too ("Also draw one for me, at grown-up detail"), and it renders
    # before the characters popover.
    picker = next(
        popover
        for popover in at.get("popover")
        if any(
            (checkbox.key or "").startswith("character_pick_")
            for checkbox in popover.get("checkbox")
        )
    )
    images = picker.get("image")
    assert len(images) == 2
    # Each st.image is served from a content-hashed URL, so two different
    # portraits produce two different URLs; two identical rows (the defect)
    # would have produced the same one twice, or none at all.
    urls = {tuple(image.value) for image in images}
    assert len(urls) == 2
    assert ida_person_id and ida_teddy_id  # both saved; ids only needed above


def test_the_add_screen_offers_a_route_to_connect_when_no_key_is_present(
    monkeypatch,
) -> None:
    """FB-08: with no drawing service connected, "Draw them" rendered
    disabled with no explanation and no route to the Connect screen
    anywhere on the page — a dead end for a parent exploring the cast
    before typing an idea, which the settings-line popover's own copy
    invites them to do."""

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.run()

    assert not at.exception
    assert not any(button.label == "Draw them" for button in at.button)
    captions = " ".join(str(caption.value) for caption in at.caption)
    assert "connect" in captions.lower()

    connect_button = next(
        button for button in at.button if button.label == "Connect a provider"
    )
    connect_button.click().run()

    assert at.session_state["screen"] == "connect"
    assert at.session_state["connect_return"] == "characters"

    # _continue_after_connection only knew "generate", "studio" and "result"
    # as valid places to send a parent back to; without "characters" in that
    # set, connecting here would have bounced to the homepage's idea screen
    # instead of back to the cast the parent was trying to build.
    monkeypatch.setattr(generators, "check_provider_connection", lambda *a, **k: {})
    key_box = next(
        widget for widget in at.text_input if widget.label == "OpenAI API key"
    )
    at = key_box.set_value("sk-newly-pasted").run()
    at = next(button for button in at.button if button.label == "Connect").click().run()

    assert not at.exception
    assert at.session_state["screen"] == "characters"


def test_a_privacy_statement_is_on_the_characters_screen_itself() -> None:
    """FB-09: the only screen that asks for a photograph of a child said
    nothing about where it goes; the disclosure lived only on Doodle
    Studio's About tab, a route this journey never visits."""

    at = _characters_screen()

    captions = " ".join(str(caption.value) for caption in at.caption).lower()
    assert "photograph" in captions
    assert "sent" in captions
    assert "removing a character" in captions
    assert "deletes" in captions


def test_redrawing_a_portrait_is_disabled_when_the_provider_cannot_use_references(
    monkeypatch,
) -> None:
    """Carried concern: "Redraw their portrait" disabled only on a missing
    key, not on a connected provider that cannot accept reference pictures
    at all (Recraft). It used to fail after the click instead of explaining
    itself in advance, the way the "Add a character" section already does."""

    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )
    save_settings({**load_settings(), "image_provider": "recraft"})
    monkeypatch.setenv("RECRAFT_API_TOKEN", "r-test")

    at = _characters_screen()

    assert not at.exception
    redraw = next(
        button for button in at.button if button.key == f"redraw_character_{ida_id}"
    )
    assert redraw.disabled is True
    captions = " ".join(str(caption.value) for caption in at.caption)
    assert "recraft cannot draw from a picture" in captions.lower()
