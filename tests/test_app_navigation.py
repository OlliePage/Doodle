"""Back and Forward at the top of every screen, driven on the real Streamlit
runtime.

Back buttons used to be dotted about, one per screen and each with its own
idea of where it led, while the browser's own Back did nothing useful. The app
now keeps one trail of where it has been. These tests press the bar's arrows;
the browser's own buttons report through a small listener in the page, which
the test runner cannot run, so those were checked in Chrome.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import list_library_items, record_doodle

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _arrow(at: AppTest, label: str):
    # Matched exactly: the wordmark's own button is labelled "Doodle, back to
    # the homepage", which a fragment match on "back" would find first.
    for button in at.button:
        if button.label == label:
            return button
    raise AssertionError(f"no {label} arrow; saw {[b.label for b in at.button]}")


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def _scripts(at: AppTest) -> list[str]:
    return [element.proto.body for element in at.get("html")]


def test_the_arrows_start_with_nowhere_to_go() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    assert _arrow(at, "Back").disabled
    assert _arrow(at, "Forward").disabled


def test_back_from_history_shows_the_same_doodle_and_forward_returns() -> None:
    at = _result_screen()
    doodle_id = at.session_state["current_doodle_id"]
    assert doodle_id

    at = _button(at, "history").click().run()
    assert at.session_state["screen"] == "history"

    at = _arrow(at, "Back").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_doodle_id"] == doodle_id

    at = _arrow(at, "Forward").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "history"


def test_after_new_doodle_back_reopens_the_doodle_from_history() -> None:
    """New doodle empties the screen, so there is no doodle in memory to go
    back to; Back reopens it from History instead of landing on a result
    screen with nothing on it."""

    at = _result_screen()
    doodle_id = at.session_state["current_doodle_id"]

    at = _button(at, "new doodle").click().run()
    assert at.session_state["screen"] == "home"
    assert at.session_state["current_raw"] is None

    at = _arrow(at, "Back").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_doodle_id"] == doodle_id
    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["quick_pdf"]


def test_the_back_arrow_moves_the_browser_once_and_only_once() -> None:
    """The arrow moves the app at once, then asks the browser to step back so
    its address and its own Back button agree with the app. The request must
    not repeat on the next unrelated rerun, or the browser would keep going."""

    at = _result_screen()
    at = _button(at, "history").click().run()

    at = _arrow(at, "Back").click().run()
    assert any("window.history.back()" in script for script in _scripts(at))

    at = at.run()
    assert not any("window.history.back()" in script for script in _scripts(at))


def test_going_somewhere_new_after_back_drops_the_way_forward() -> None:
    at = _result_screen()
    at = _button(at, "history").click().run()
    at = _arrow(at, "Back").click().run()
    assert not _arrow(at, "Forward").disabled

    at = _button(at, "new doodle").click().run()
    assert _arrow(at, "Forward").disabled


def test_a_fresh_load_reopens_the_doodle_named_in_the_address() -> None:
    """A refresh starts a new session with nothing in memory; the address
    names the doodle, so it comes back from History ready to print."""

    item_id = record_doodle(
        raw_image=ARTWORK,
        processed_image=ARTWORK,
        title="Blue dinosaur",
        metadata={"concept": "a blue dinosaur", "source": "test"},
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["screen"] = "result"
    at.query_params["doodle"] = item_id
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_doodle_id"] == item_id
    assert at.session_state["quick_pdf"]
    assert at.session_state["generation_idea"] == "a blue dinosaur"


def test_an_address_naming_the_drawing_screen_draws_nothing(monkeypatch) -> None:
    """The drawing screen spends money the moment it is shown, so no address
    can lead to it: a bookmark or an edited address opens the homepage."""

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls: list[dict] = []
    monkeypatch.setattr(
        generators, "generate_with_provider", lambda **kwargs: calls.append(kwargs)
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params["screen"] = "generate"
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert calls == []


def test_back_while_drawing_keeps_what_is_drawn_and_draws_nothing_more(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls: list[str] = []

    def fake_generate(**kwargs):
        prompt = kwargs["prompts"][0]
        calls.append(prompt)
        if len(calls) == 2:
            # Ends this run on the drawing screen with one of two pictures
            # drawn: the moment a parent would press Back.
            import streamlit as st

            st.stop()
        return [
            GeneratedArtwork(
                image_bytes=ARTWORK, prompt=prompt, provider="OpenAI", model="m"
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(
        variations,
        "build_variation_briefs",
        lambda idea, count, **kwargs: [
            f"reading {i + 1} of {idea}" for i in range(count)
        ],
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at = at.segmented_control(key="home_alternatives").set_value(2).run()
    at.text_input(key="home_prompt").set_value("a dinosaur washing a fire engine")
    at = _button(at, "draw it").click().run()
    assert at.session_state["screen"] == "generate"
    assert len(calls) == 2

    at = _arrow(at, "Back").click().run()
    assert not at.exception
    assert len(calls) == 2, "Back must never start another paid drawing"
    # With a picture already drawn and paid for, Back is Stop: it lands on
    # that picture rather than walking away from it.
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_raw"] == ARTWORK
    assert len(list_library_items()) == 1


def test_back_while_drawing_with_nothing_drawn_returns_to_the_idea(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    calls: list[dict] = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        # Ends this run on the drawing screen before the first picture is
        # back: the moment a parent would press Back.
        import streamlit as st

        st.stop()

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.text_input(key="home_prompt").set_value("a dinosaur washing a fire engine")
    at = _button(at, "draw it").click().run()
    assert at.session_state["screen"] == "generate"

    at = _arrow(at, "Back").click().run()
    assert not at.exception
    assert len(calls) == 1, "Back must never start another paid drawing"
    assert at.session_state["screen"] == "home"
    assert at.session_state["home_prompt"] == "a dinosaur washing a fire engine"
    assert list_library_items() == []
