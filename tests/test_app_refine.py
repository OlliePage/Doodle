"""The refine control, driven on the real Streamlit runtime.

Every button here is clicked, never merely asserted to exist. A recovery button
shipped broken past that omission on 2026-08-30.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import history
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _art(tag: str) -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=ARTWORK, prompt=tag, provider="OpenAI", model="gpt-image-2"
    )


def _studio_with_chain(chain) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["doodle_versions"] = chain
    at.session_state["current_version"] = len(chain) - 1
    at.run()
    return at


def _change_box(at: AppTest):
    for widget in at.text_input:
        if widget.label == "Make a change":
            return widget
    raise AssertionError("the refine box is missing")


def _captions(at: AppTest) -> str:
    return " ".join(caption.value for caption in at.caption)


def test_the_refine_box_appears_once_a_picture_exists() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    assert not at.exception
    assert _change_box(at) is not None


def test_the_limitation_is_stated_next_to_the_box() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    captions = _captions(at)
    assert "redrawn" in captions
    assert "costs one generation" in captions


def test_submitting_with_no_key_explains_rather_than_crashing() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    _change_box(at).set_value("give it a hat")

    submits = [b for b in at.button if b.label == "Change it"]
    assert submits, "no submit button on the refine form"
    submits[0].click().run()

    assert not at.exception
    assert any("connected" in error.value.lower() for error in at.error)


def test_submitting_an_empty_instruction_does_nothing() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    submits = [b for b in at.button if b.label == "Change it"]
    submits[0].click().run()

    assert not at.exception
    assert len(at.session_state["doodle_versions"]) == 1


def test_the_version_strip_shows_the_chain_and_can_step_back() -> None:
    chain = history.start(_art("original"))
    chain = history.append(chain, _art("hatted"), "add a hat", parent=0)
    at = _studio_with_chain(chain)

    captions = _captions(at)
    assert "2 versions" in captions
    assert "add a hat" in captions

    back = [b for b in at.button if "Go back" in b.label]
    assert back, "no way to return to an earlier version"

    # Click it, do not merely assert it renders.
    back[0].click().run()
    assert not at.exception
    assert at.session_state["current_version"] == 0


def test_stepping_back_does_not_delete_later_versions() -> None:
    chain = history.start(_art("original"))
    chain = history.append(chain, _art("hatted"), "add a hat", parent=0)
    at = _studio_with_chain(chain)

    back = [b for b in at.button if "Go back" in b.label]
    back[0].click().run()

    assert len(at.session_state["doodle_versions"]) == 2


def test_a_single_version_shows_no_strip() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    assert not [b for b in at.button if "Go back" in b.label]
    assert "versions drawn" not in _captions(at)


def test_the_result_screen_carries_the_same_control() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.session_state["doodle_versions"] = history.start(_art("original"))
    at.session_state["current_version"] = 0
    at.run()

    assert not at.exception
    assert _change_box(at) is not None
