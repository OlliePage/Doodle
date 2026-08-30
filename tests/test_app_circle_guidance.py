"""End-to-end checks of the circle-sheet screen on the real Streamlit runtime.

The other app test drives a hand-written fake Streamlit, which cannot tell
whether a widget rendered or what it said. These use Streamlit's own AppTest
runner, which caught a gap the unit tests could not: a sheet that holds no
badges is returned as a zero-capacity plan rather than raised as an error, so
the guidance never fired and the screen simply reported "0 circles".
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _circle_sheet() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = (
        PROJECT_ROOT / "assets" / "demo_dinosaur.png"
    ).read_bytes()
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    for radio in at.radio:
        if radio.label == "Output format":
            return radio.set_value("A4 circle sheet").run()
    raise AssertionError("Output format control not found")


def _number(at: AppTest, label: str):
    for widget in at.number_input:
        if widget.label == label:
            return widget
    raise AssertionError(f"{label} not found")


def _captions(at: AppTest) -> list[str]:
    return [caption.value for caption in at.caption]


def test_the_circle_sheet_renders_without_error() -> None:
    at = _circle_sheet()
    assert not at.exception
    assert not at.error


def test_the_badge_legend_names_all_three_boundaries() -> None:
    at = _circle_sheet()
    body = " ".join(block.value for block in at.markdown)
    assert "where the paper is cut" in body
    assert "visible face once pressed" in body
    assert "faces, eyes and text" in body


def test_fitting_the_whole_picture_is_the_default_and_is_explained() -> None:
    at = _circle_sheet()
    controls = [s for s in at.segmented_control if s.label == "Artwork fit"]
    assert controls, "the artwork fit control is missing"
    assert controls[0].value == "Fit the whole picture"
    assert any("nothing is lost" in caption for caption in _captions(at))


def test_filling_the_circle_warns_that_corners_are_lost() -> None:
    at = _circle_sheet()
    at.segmented_control[0].set_value("Fill the circle").run()
    assert not at.exception
    assert any("corners are cut away" in caption for caption in _captions(at))


def test_a_sheet_that_holds_no_badges_offers_a_margin_that_works() -> None:
    at = _circle_sheet()
    _number(at, "Paper cut diameter (mm)").set_value(190.0).run()
    _number(at, "Outer margin (mm)").set_value(40.0).run()

    assert not at.exception
    assert any("No badges fit on the sheet" in error.value for error in at.error)

    fixes = [button.label for button in at.button if "margin" in button.label.lower()]
    assert fixes, "no one-click margin fix was offered"
    assert any("Outer margin" in caption for caption in _captions(at))


def test_impossible_diameters_are_explained_rather_than_dumped() -> None:
    at = _circle_sheet()
    _number(at, "Safe artwork diameter (mm)").set_value(120.0).run()

    assert not at.exception
    assert any("diameters cannot all be true" in error.value for error in at.error)
    assert any("diameter boxes" in caption for caption in _captions(at))


def test_the_homepage_shows_one_prompt_bar_and_a_hint() -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()

    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert len(at.text_input) == 1
    body = " ".join(block.value for block in at.markdown)
    assert "Press Enter to draw" in body
    assert "doodle-logo--hero" in body


def _all_rendered(at: AppTest) -> str:
    blocks = [block.value for block in at.markdown]
    blocks += [block.proto.body for block in at.get("html")]
    return " ".join(blocks)


def test_the_build_badge_survives_every_screen() -> None:
    # This branch added three screens that each end in st.stop(), any of which
    # could have left the badge unreached.
    home = AppTest.from_file(APP, default_timeout=60)
    home.run()
    assert "doodle-build" in _all_rendered(home)

    home.text_input[0].set_value("A bear flying a kite").run()
    assert home.session_state["screen"] == "connect"
    assert "doodle-build" in _all_rendered(home)

    assert "doodle-build" in _all_rendered(_circle_sheet())


def test_an_idea_with_no_key_routes_to_the_connection_screen() -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.text_input[0].set_value("A bear flying a kite").run()

    assert not at.exception
    assert at.session_state["screen"] == "connect"
    assert at.session_state["generation_idea"] == "A bear flying a kite"
    assert at.radio[0].options == ["OpenAI", "Google Gemini", "Recraft"]
    assert any("API keys" in button.label for button in at.get("link_button"))


def test_clicking_the_margin_fix_actually_applies_it() -> None:
    # The earlier test asserted only that the button existed. Clicking it raised
    # StreamlitAPIException, because assigning to a widget's session-state key
    # from the script body is refused once the widget has been instantiated.
    at = _circle_sheet()
    _number(at, "Paper cut diameter (mm)").set_value(190.0).run()
    _number(at, "Outer margin (mm)").set_value(40.0).run()

    fixes = [button for button in at.button if "margin" in button.label.lower()]
    assert fixes, "no one-click margin fix was offered"

    suggested = float(fixes[0].label.split()[-2])
    fixes[0].click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert _number(at, "Outer margin (mm)").value == suggested


def test_the_applied_margin_makes_the_badges_fit() -> None:
    # A fix that applies cleanly but still does not fit would be worse than none.
    at = _circle_sheet()
    _number(at, "Paper cut diameter (mm)").set_value(190.0).run()
    _number(at, "Outer margin (mm)").set_value(40.0).run()

    fixes = [button for button in at.button if "margin" in button.label.lower()]
    fixes[0].click().run()

    assert not at.exception
    assert not any("No badges fit" in error.value for error in at.error)


def test_gemini_users_are_not_given_recrafts_instructions() -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.text_input[0].set_value("A bear flying a kite").run()
    assert at.session_state["screen"] == "connect"

    at.radio[0].set_value("Google Gemini").run()
    captions = " ".join(caption.value for caption in at.caption)
    assert "AI Studio" in captions
    assert "Recraft" not in captions
    assert any("billing" in button.label.lower() for button in at.get("link_button"))
