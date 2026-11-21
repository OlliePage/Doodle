"""Which image model drew a picture, and drawing the same idea on another.

Providers retire models every few months, and the only place the model was
named used to be the Studio sidebar, which the children's screens hide. These
drive the real Streamlit runtime and click the switch rather than asserting it
exists.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import load_settings, save_library_item, save_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _captions(at: AppTest) -> list[str]:
    return [str(caption.value) for caption in at.caption]


def _result_screen(metadata: dict) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.session_state["current_title"] = "a blue dinosaur"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["current_metadata"] = metadata
    at.run()
    return at


def test_the_waiting_screen_names_the_model_doing_the_drawing(monkeypatch) -> None:
    settings = load_settings()
    settings["openai_model"] = "gpt-image-1.5"
    save_settings(settings)

    def never_returns(**kwargs):
        raise RuntimeError("stand-in for a drawing that is still going")

    monkeypatch.setattr(generators, "generate_with_provider", never_returns)
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.run()

    assert "Drawing with OpenAI · gpt-image-1.5" in _captions(at)


def test_the_finished_picture_says_which_model_drew_it() -> None:
    at = _result_screen({"source": "OpenAI", "model": "gpt-image-2"})

    assert not at.exception
    assert "Drawn with OpenAI · gpt-image-2" in _captions(at)


def test_a_sample_picture_claims_no_model() -> None:
    at = _result_screen({"source": "Demo", "model": "dinosaur"})

    assert not any(caption.startswith("Drawn with") for caption in _captions(at))


def test_drawing_again_with_another_model_uses_it_and_keeps_it(monkeypatch) -> None:
    seen_models: list[str] = []

    def fake_generate(**kwargs):
        seen_models.append(kwargs["model"])
        return [
            GeneratedArtwork(
                image_bytes=ARTWORK,
                prompt=kwargs["prompts"][0],
                provider="OpenAI",
                model=kwargs["model"],
            )
        ]

    monkeypatch.setattr(generators, "generate_with_provider", fake_generate)
    monkeypatch.setattr(
        variations,
        "build_variation_briefs",
        lambda idea, count, **kwargs: [f"reading {i} of {idea}" for i in range(count)],
    )

    at = _result_screen({"source": "OpenAI", "model": "gpt-image-2"})
    at.selectbox(key="redraw_model").set_value("gpt-image-1-mini")
    at = at.button(key="redraw_with_model").click().run()

    assert not at.exception
    assert seen_models and set(seen_models) == {"gpt-image-1-mini"}
    assert at.session_state["screen"] == "result"
    assert "Drawn with OpenAI · gpt-image-1-mini" in _captions(at)
    assert load_settings()["openai_model"] == "gpt-image-1-mini"


def test_history_cards_name_the_model() -> None:
    save_library_item(
        processed_image=ARTWORK,
        raw_image=ARTWORK,
        title="Blue dinosaur",
        metadata={"source": "Google Gemini", "model": "gemini-nano-banana-2.1"},
    )
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "history"
    at.run()

    assert "Source: Google Gemini · gemini-nano-banana-2.1" in _captions(at)
