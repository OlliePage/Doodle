from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / "app.py")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    # Without this the homepage reads the real library in ~/.doodle, and the
    # corner link to it appears or not depending on whose machine is running.
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))


def _homepage() -> AppTest:
    return AppTest.from_file(APP, default_timeout=60).run()


def _draw_it(app: AppTest):
    for button in app.button:
        if button.label == "Draw it":
            return button
    raise AssertionError(f"no Draw it button; saw {[b.label for b in app.button]}")


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
    _draw_it(app).click().run()

    assert app.session_state["screen"] != "home"
    assert app.session_state["generation_idea"] == "a red bus"


def test_submitting_an_empty_prompt_stays_put() -> None:
    app = _homepage()
    _draw_it(app).click().run()

    assert app.session_state["screen"] == "home"


def test_submitting_only_whitespace_stays_put() -> None:
    app = _homepage()
    app.text_input[0].set_value("   ").run()
    _draw_it(app).click().run()

    assert app.session_state["screen"] == "home"
