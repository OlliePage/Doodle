from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


def _homepage() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def test_typing_alone_does_not_leave_the_homepage() -> None:
    """The reported bug: three letters typed jumped to the next screen.

    The input carried an on_change callback, and Streamlit fires that when the
    box loses focus as well as on Enter, so clicking anywhere sent a half-typed
    prompt onward.
    """

    app = _homepage()
    app.text_input[0].set_value("dfa").run()

    assert app.session_state["screen"] == "home"
    assert len(app.text_input) == 1


def test_the_button_is_what_leaves_the_homepage() -> None:
    app = _homepage()
    app.text_input[0].set_value("a red bus").run()
    app.button[0].click().run()

    assert app.session_state["screen"] != "home"
    assert app.session_state["generation_idea"] == "a red bus"


def test_submitting_an_empty_prompt_stays_put() -> None:
    app = _homepage()
    app.button[0].click().run()

    assert app.session_state["screen"] == "home"


def test_submitting_only_whitespace_stays_put() -> None:
    app = _homepage()
    app.text_input[0].set_value("   ").run()
    app.button[0].click().run()

    assert app.session_state["screen"] == "home"
