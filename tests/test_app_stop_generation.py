"""Stopping a batch drawing partway through, and what survives it.

Each picture Doodle draws is its own paid call. Until now the whole batch —
one reading of an idea, several alternatives, or a pair — was drawn inside a
single blocking call, so nothing on the page could be pressed while it ran
and there was no way to change your mind. Drawing one picture per script run
instead means the page comes back to life between pictures, live enough to
carry a stop button and a count of progress. These tests hold that in place:
what stopping keeps, what it throws away, and that it actually stops the
next request from ever being sent.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.characters import save_character
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
ARTWORK = (ASSETS / "demo_dinosaur.png").read_bytes()
OTHER = (ASSETS / "demo_robot_balloons.png").read_bytes()


def _one_pixel_photo() -> bytes:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (1, 1), (180, 90, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


PHOTO_BYTES = _one_pixel_photo()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _homepage() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def _fake_briefs(idea, count, **kwargs):
    return [f"reading {index + 1} of {idea}" for index in range(count)]


def test_stopping_after_some_pictures_keeps_them_and_reaches_the_result_screen(
    monkeypatch,
) -> None:
    """Two of four drawn, then stopped: land on the result screen with those
    two, able to pick between them, exactly as if two had been asked for."""

    calls: list[str] = []
    images = [ARTWORK, OTHER, ARTWORK, OTHER]

    def fake_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        artwork = GeneratedArtwork(
            image_bytes=images[(len(calls) - 1) % len(images)],
            prompt=prompt,
            provider="OpenAI",
            model="gpt-image-2",
        )
        if len(calls) == 2:
            # Stands in for the parent pressing Stop while this picture, the
            # second of four, was being drawn. The request in flight still
            # finishes and is still charged — that is this picture landing
            # here at all — but nothing after it should ever be requested.
            import streamlit as st

            st.session_state["generation_stop_requested"] = True
        return [artwork]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(4).run()
    at.text_input(key="home_prompt").set_value(
        "naomi and aria go camping with mummy in a forest with a stream"
    )
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert len(calls) == 2, "stopping must prevent the remaining drawing calls"
    assert at.session_state["screen"] == "result"
    assert len(at.session_state["candidates"]) == 2
    assert at.session_state["quick_processed"]
    # The plan is put away once the batch is over, stopped or not, so a
    # later "Draw this idea again" starts a fresh one rather than resuming.
    assert at.session_state["generation_jobs"] == []
    assert at.session_state["generation_stop_requested"] is False


def test_stopping_before_anything_is_drawn_returns_home_with_the_idea_intact(
    monkeypatch,
) -> None:
    def explode(**kwargs):
        raise AssertionError("stopping before anything is drawn must draw nothing")

    monkeypatch.setattr(generators, "generate_with_provider", explode)

    idea = "naomi and aria go camping with mummy in a forest with a stream"
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = idea
    at.session_state["quick_mode"] = "ai"
    # Stands in for the parent pressing Stop before the first request is
    # even sent: nothing has been drawn, so there is nothing to keep.
    at.session_state["generation_stop_requested"] = True
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert at.session_state["home_prompt"] == idea
    assert at.session_state["current_raw"] is None
    assert at.session_state["generation_stop_requested"] is False


def test_stopping_prevents_further_drawing_calls_being_made(monkeypatch) -> None:
    """A narrower, more literal reading of the same guarantee as the test
    above: once stopped, the count of calls made never grows further, even
    though the batch asked for more than one picture."""

    calls: list[str] = []

    def fake_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        if len(calls) == 1:
            import streamlit as st

            st.session_state["generation_stop_requested"] = True
        return [
            GeneratedArtwork(
                image_bytes=ARTWORK,
                prompt=prompt,
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(3).run()
    at.text_input(key="home_prompt").set_value("a dinosaur washing a fire engine")
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert len(calls) == 1
    assert at.session_state["screen"] == "result"
    assert at.session_state["candidates"] == []


def test_pairing_still_draws_exactly_two_pictures_one_at_a_time(monkeypatch) -> None:
    """The alternatives count and the grown-up pairing interact: with
    pairing on, exactly two pictures are drawn whatever the alternatives
    count says, one at a time now rather than in one call."""

    calls: list[str] = []

    def fake_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        is_grown_up = "150 or more small colouring regions" in prompt
        return [
            GeneratedArtwork(
                image_bytes=OTHER if is_grown_up else ARTWORK,
                prompt=prompt,
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)

    # The pair's second sheet is drawn FROM the first since 2026-08-31, so it
    # goes through the reference-carrying call and this has to count both.
    def fake_refine(**kwargs):
        calls.append(kwargs["prompt"])
        return GeneratedArtwork(
            image_bytes=OTHER,
            prompt=kwargs["prompt"],
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)

    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(4).run()
    at = at.checkbox(key="home_pair_grown_up").set_value(True).run()
    at.text_input(key="home_prompt").set_value("a fox in a wood")
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert len(calls) == 2, "pairing draws exactly two, whatever alternatives says"
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["pair_raw"] == OTHER
    assert at.session_state["candidates"] == []


def test_a_cast_scene_is_still_drawn_one_picture_at_a_time(monkeypatch) -> None:
    """Scenes starring saved characters go through refine_with_provider, a
    different call from an ordinary idea's generate_with_provider, and carry
    reference photographs. That path must also draw one picture per script
    run, and stopping it must work the same way."""

    ida_id = save_character(
        photo=PHOTO_BYTES, portrait=ARTWORK, name="Ida", kind="person", marks=""
    )
    calls: list[dict] = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        artwork = GeneratedArtwork(
            image_bytes=ARTWORK if len(calls) == 1 else OTHER,
            prompt=kwargs["prompt"],
            provider="OpenAI",
            model="gpt-image-2",
        )
        if len(calls) == 1:
            import streamlit as st

            st.session_state["generation_stop_requested"] = True
        return artwork

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(3).run()
    at.checkbox(key=f"character_pick_{ida_id}").set_value(True).run()
    at.text_input(key="home_prompt").set_value("a picnic in the park")
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert len(calls) == 1, "stopping must prevent further reference-carrying calls"
    assert all(kwargs["reference_images"] for kwargs in calls)
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_metadata"]["generation"]["characters"] == [ida_id]


def test_the_built_in_sample_path_gains_no_stop_button() -> None:
    """The sample path draws no pictures at all, so a stop button here would
    control nothing — it would just be a control that cannot help."""

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["quick_mode"] = "demo"
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert not any("stop" in button.label.lower() for button in at.button)


def _frozen_mid_batch(monkeypatch, *, alternatives: int, crash_on_call: int) -> AppTest:
    """Render the drawing screen genuinely partway through a batch.

    AppTest only ever returns a script's fully-settled state, and this
    screen always settles by moving itself on — to the result screen, home,
    or connect — so there is no ordinary way to inspect the "generate"
    screen's own frame while a batch is actually in progress. Raising an
    error the app does not catch stops the script exactly where it is,
    after the calls before it succeeded and rendered normally, which is
    enough to look at what that frame actually contains: the progress line,
    the settings row, and the stop button.
    """

    from colouring_factory.storage import load_settings, save_settings

    calls: list[str] = []

    def fake_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        if len(calls) == crash_on_call:
            raise RuntimeError("stand-in for an unrelated crash, to freeze this frame")
        return [
            GeneratedArtwork(
                image_bytes=ARTWORK,
                prompt=prompt,
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)
    save_settings({**load_settings(), "quick_alternatives": alternatives})

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a fox in a wood"
    at.session_state["quick_mode"] = "ai"
    at.run()
    assert at.session_state["screen"] == "generate", (
        "the frame under test must not have moved on"
    )
    assert any("stand-in" in str(e.value) for e in at.exception), [
        str(e.value) for e in at.exception
    ]
    return at


def test_the_progress_line_names_where_the_parent_is(monkeypatch) -> None:
    """ "Drawing 2 of 4", not a progress bar with an invented percentage."""

    at = _frozen_mid_batch(monkeypatch, alternatives=4, crash_on_call=2)

    progress = " ".join(
        str(m.value) for m in at.markdown if "drawing-progress" in str(m.value)
    )
    assert "Drawing 2 of 4" in progress
    assert not at.get("progress"), "a real progress bar has no true percentage here"


def test_the_stop_button_is_genuinely_on_the_drawing_screen(monkeypatch) -> None:
    at = _frozen_mid_batch(monkeypatch, alternatives=4, crash_on_call=2)
    assert any("stop" in button.label.lower() for button in at.button)


def test_the_homepage_settings_row_is_hidden_on_the_drawing_screen(monkeypatch) -> None:
    """The settings line answers questions this screen has already moved
    past. It is never rendered here (_render_home_options is only called
    from the homepage), but while a picture is drawn the previous frame's
    copy of it used to linger on screen, un-truncated only by CSS rules
    that live on the homepage and are not carried over here. The fix hides
    it outright rather than relying on it not being drawn."""

    at = _frozen_mid_batch(monkeypatch, alternatives=4, crash_on_call=2)

    styles = " ".join(str(m.value) for m in at.markdown if "<style>" in str(m.value))
    assert ".st-key-doodle-home-settings" in styles
    assert "display:none" in styles.replace(" ", "")


def test_a_failure_partway_through_a_batch_keeps_what_succeeded(monkeypatch) -> None:
    """A stop the parent presses keeps what has been drawn; a failure used
    to discard the whole batch instead, including pictures already paid
    for. The second of four alternatives fails here — the first, already
    charged, must still reach the result screen."""

    calls: list[str] = []

    def failing_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        if len(calls) == 2:
            raise GeneratorError(
                "OpenAI declined that description.", provider="OpenAI", code="content"
            )
        return [
            GeneratedArtwork(
                image_bytes=ARTWORK,
                prompt=prompt,
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", failing_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(4).run()
    at.text_input(key="home_prompt").set_value(
        "naomi and aria go camping with mummy in a forest with a stream"
    )
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert len(calls) == 2, (
        "a failure must stop the rest of the batch, like a stop does"
    )
    assert at.session_state["screen"] == "result"
    assert at.session_state["quick_processed"]


def test_the_result_screen_explains_a_partial_batch_failure(monkeypatch) -> None:
    calls: list[str] = []

    def failing_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        if len(calls) == 2:
            raise GeneratorError(
                "OpenAI declined that description.", provider="OpenAI", code="content"
            )
        return [
            GeneratedArtwork(
                image_bytes=ARTWORK,
                prompt=prompt,
                provider="OpenAI",
                model="gpt-image-2",
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", failing_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = _homepage()
    at = at.segmented_control(key="home_alternatives").set_value(4).run()
    at.text_input(key="home_prompt").set_value(
        "naomi and aria go camping with mummy in a forest with a stream"
    )
    at = _button(at, "draw it").click().run()

    assert not at.exception
    notices = " ".join(str(w.value) for w in at.warning).lower()
    assert "could not be drawn" in notices
    assert "declined" in notices


def test_a_failure_before_anything_is_drawn_still_routes_home(monkeypatch) -> None:
    """No concrete reason for this case to differ from before: with nothing
    yet collected there is nothing to keep, so the existing route-to-home
    (or Connect) behaviour is unchanged."""

    def failing_generate(**kwargs):
        raise GeneratorError(
            "OpenAI declined that description.", provider="OpenAI", code="content"
        )

    monkeypatch.setattr(generators, "generate_with_provider", failing_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = _homepage()
    at.text_input(key="home_prompt").set_value("a bear flying a kite")
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert at.session_state["home_prompt"] == "a bear flying a kite"
