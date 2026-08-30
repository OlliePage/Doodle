"""Getting to your saved doodles, driven on the real Streamlit runtime.

Saving worked and said so; nothing anywhere led back to what had been saved.
Every route added to fix that is clicked here, not merely asserted to render.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory.storage import list_library_items, save_library_item

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _seed(title: str = "Blue dinosaur") -> str:
    return save_library_item(
        processed_image=ARTWORK,
        raw_image=ARTWORK,
        title=title,
        metadata={"source": "test"},
    )


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _has_button(at: AppTest, fragment: str) -> bool:
    return any(fragment.lower() in button.label.lower() for button in at.button)


def _text(at: AppTest) -> str:
    parts = [element.value for element in at.caption]
    parts += [element.value for element in at.markdown]
    parts += [element.value for element in at.success]
    parts += [element.value for element in at.info]
    parts += [element.value for element in at.warning]
    return " ".join(str(part) for part in parts)


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


def test_the_homepage_stays_bare_until_something_is_saved() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    assert not _has_button(at, "saved doodles")


def test_the_homepage_counts_saved_doodles_and_opens_them() -> None:
    _seed()
    _seed("Red tractor")

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    route = _button(at, "saved doodles")
    assert "(2)" in route.label

    at = route.click().run()
    assert not at.exception
    assert at.session_state["screen"] == "library"
    assert "Blue dinosaur" in _text(at)
    assert "Red tractor" in _text(at)


def test_saving_a_doodle_offers_the_way_back_to_it() -> None:
    at = _result_screen()
    assert not at.exception

    at = _button(at, "save to your doodles").click().run()
    assert len(list_library_items()) == 1
    assert "Saved to your doodles" in _text(at)

    at = _button(at, "see your saved doodles").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "library"
    assert "Blue dinosaur" in _text(at)


def test_the_library_returns_to_the_doodle_you_came_from() -> None:
    at = _result_screen()
    at = _button(at, "save to your doodles").click().run()
    at = _button(at, "see your saved doodles").click().run()

    at = _button(at, "back to your doodle").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "result"


def test_opening_a_saved_doodle_loads_it_into_the_studio() -> None:
    _seed()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "library"
    at.run()

    at = _button(at, "open").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "studio"
    assert at.session_state["current_title"] == "Blue dinosaur"
    assert at.session_state["current_raw"] == ARTWORK
    assert "Blue dinosaur is open" in _text(at)


def test_deleting_a_saved_doodle_asks_before_it_happens() -> None:
    _seed()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "library"
    at.run()

    at = _button(at, "delete").click().run()
    assert not at.exception
    assert len(list_library_items()) == 1
    assert "cannot be undone" in _text(at)

    at = _button(at, "keep it").click().run()
    assert len(list_library_items()) == 1

    at = _button(at, "delete").click().run()
    at = _button(at, "delete for good").click().run()
    assert not at.exception
    assert list_library_items() == []
    assert "no saved doodles yet" in _text(at)


def test_the_studio_tab_shows_the_same_saved_doodles() -> None:
    _seed()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.run()
    assert not at.exception
    assert "Blue dinosaur" in _text(at)
