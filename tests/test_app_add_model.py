"""Adding an image model Doodle does not ship with, from the Studio sidebar.

Providers retire models every few months. These click every control on the
real Streamlit runtime and check the setting that the next drawing reads.
"""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators
from colouring_factory.generators import GeneratorError
from colouring_factory.storage import load_settings

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _studio() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.run()
    return at


def _model_picker(at: AppTest):
    return next(box for box in at.sidebar.selectbox if box.label == "Image model")


def test_a_typed_model_joins_the_list_and_becomes_the_one_in_use() -> None:
    at = _studio()
    at.sidebar.text_input(key="new_model_name").set_value("gpt-image-9")
    at = at.sidebar.button(key="add_model").click().run()

    assert not at.exception
    settings = load_settings()
    assert settings["openai_model"] == "gpt-image-9"
    assert settings["openai_added_models"] == ["gpt-image-9"]
    picker = _model_picker(at)
    assert "gpt-image-9" in picker.options
    assert picker.value == "gpt-image-9"


def test_an_added_model_can_be_removed_and_the_default_returns() -> None:
    at = _studio()
    at.sidebar.text_input(key="new_model_name").set_value("gpt-image-9")
    at = at.sidebar.button(key="add_model").click().run()
    at = at.sidebar.button(key="remove_model").click().run()

    assert not at.exception
    settings = load_settings()
    assert settings["openai_added_models"] == []
    assert _model_picker(at).value == "gpt-image-2"
    assert "gpt-image-9" not in _model_picker(at).options


def test_asking_the_provider_offers_only_models_doodle_lacks(monkeypatch) -> None:
    monkeypatch.setattr(
        generators,
        "list_image_models",
        lambda provider_id, api_key: ["gpt-image-1.5", "gpt-image-2", "gpt-image-3"],
    )
    at = _studio()
    at = at.sidebar.button(key="find_models").click().run()

    labels = [button.label for button in at.sidebar.button]
    assert "Add gpt-image-3" in labels
    assert "Add gpt-image-2" not in labels

    at = at.sidebar.button(key="add_found_gpt-image-3").click().run()
    assert not at.exception
    assert load_settings()["openai_model"] == "gpt-image-3"
    assert _model_picker(at).value == "gpt-image-3"


def test_a_failed_lookup_says_why(monkeypatch) -> None:
    def refuses(provider_id, api_key):
        raise GeneratorError("OpenAI rejected the key.", code="auth")

    monkeypatch.setattr(generators, "list_image_models", refuses)
    at = _studio()
    at = at.sidebar.button(key="find_models").click().run()

    assert not at.exception
    assert any("rejected the key" in str(error.value) for error in at.sidebar.error)


class _Reply(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_openai_listing_keeps_only_image_models(monkeypatch) -> None:
    payload = {"data": [{"id": "gpt-5"}, {"id": "gpt-image-2"}, {"id": "gpt-image-3"}]}
    monkeypatch.setattr(
        generators,
        "urlopen",
        lambda request, timeout=None: _Reply(json.dumps(payload).encode()),
    )

    assert generators.list_image_models("openai", "sk-test") == [
        "gpt-image-2",
        "gpt-image-3",
    ]


def test_google_listing_strips_the_prefix_and_keeps_image_models(monkeypatch) -> None:
    captured = {}
    payload = {
        "models": [
            {"name": "models/gemini-3.5-flash-lite"},
            {"name": "models/gemini-3-pro-image"},
            {"name": "models/gemini-nano-banana-2.1"},
        ]
    }

    def fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.headers)
        return _Reply(json.dumps(payload).encode())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    assert generators.list_image_models("google", "AIza-test") == [
        "gemini-3-pro-image",
        "gemini-nano-banana-2.1",
    ]
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"
