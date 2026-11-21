"""The image model on the homepage's line of settings.

The model could only be seen or changed in the Studio sidebar, which the
homepage hides, so a parent looking at the homepage had no way to find it.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory.storage import load_settings

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _home() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def test_the_homepage_names_the_model_in_use() -> None:
    at = _home()

    assert not at.exception
    labels = [popover.proto.popover.label for popover in at.get("popover")]
    assert "gpt-image-2" in labels


def test_choosing_a_model_on_the_homepage_is_what_the_next_drawing_uses() -> None:
    at = _home()
    at = at.selectbox(key="home_model_openai").set_value("gpt-image-1.5").run()

    assert not at.exception
    assert load_settings()["openai_model"] == "gpt-image-1.5"
    assert "gpt-image-1.5" in [
        popover.proto.popover.label for popover in at.get("popover")
    ]


def test_switching_provider_on_the_homepage_shows_its_models() -> None:
    at = _home()
    at = at.selectbox(key="home_provider").set_value("Google Gemini").run()

    assert not at.exception
    assert load_settings()["image_provider"] == "google"
    assert "gemini-nano-banana-2.1" in at.selectbox(key="home_model_google").options


def test_a_model_added_on_the_homepage_becomes_the_one_in_use() -> None:
    at = _home()
    at.text_input(key="new_model_name").set_value("gpt-image-9")
    at = at.button(key="add_model").click().run()

    assert not at.exception
    assert load_settings()["openai_model"] == "gpt-image-9"
    assert at.selectbox(key="home_model_openai").value == "gpt-image-9"
