"""Seeing a doodle coloured in, without colouring what gets printed.

A page of outlines tells a child nothing about what colour water or grass
should be. This draws one coloured copy to compare against; the PDF stays
black and white, and these tests hold that line.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ASSETS = PROJECT_ROOT / "assets"
LINE_ART = (ASSETS / "demo_dinosaur.png").read_bytes()
COLOURED = (ASSETS / "demo_robot_balloons.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


@pytest.fixture
def coloured(monkeypatch):
    calls: list[dict] = []

    def fake_refine(**kwargs):
        calls.append(kwargs)
        return GeneratedArtwork(
            image_bytes=COLOURED,
            prompt=kwargs["prompt"],
            provider="OpenAI",
            model="gpt-image-2",
        )

    monkeypatch.setattr(generators, "refine_with_provider", fake_refine)
    return calls


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _has_button(at: AppTest, fragment: str) -> bool:
    return any(fragment.lower() in button.label.lower() for button in at.button)


def _captions(at: AppTest) -> str:
    return " ".join(caption.value for caption in at.caption)


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = LINE_ART
    at.session_state["quick_processed"] = LINE_ART
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def test_the_offer_to_colour_it_in_is_on_the_result_screen() -> None:
    at = _result_screen()
    assert not at.exception
    assert _has_button(at, "colour it in for me")


def test_colouring_it_in_shows_the_coloured_copy(coloured) -> None:
    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    assert len(coloured) == 1, "one generation, not one per rerun"
    assert at.session_state["showing_colours"] is True
    assert COLOURED in at.session_state["colour_previews"].values()
    assert "black and white" in _captions(at)


def test_the_printed_pdf_is_never_the_coloured_one(coloured) -> None:
    at = _result_screen()
    before = at.session_state["quick_pdf"]

    at = _button(at, "colour it in for me").click().run()
    assert at.session_state["quick_pdf"] == before
    assert at.session_state["quick_processed"] == LINE_ART


def test_the_outlines_come_back(coloured) -> None:
    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    at = _button(at, "show the outlines").click().run()
    assert not at.exception
    assert at.session_state["showing_colours"] is False
    assert _has_button(at, "show suggested colours")


def test_looking_again_costs_nothing(coloured) -> None:
    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()
    at = _button(at, "show the outlines").click().run()
    at = _button(at, "show suggested colours").click().run()

    assert not at.exception
    assert at.session_state["showing_colours"] is True
    assert len(coloured) == 1, "the coloured copy is kept, not redrawn"


def test_the_instruction_asks_to_keep_the_drawing_intact(coloured) -> None:
    at = _result_screen()
    _button(at, "colour it in for me").click().run()

    instruction = " ".join(coloured[0]["prompt"].lower().split())
    assert "keep every black outline" in instruction
    assert "do not redraw" in instruction
    # Named colours a child can check against the real thing.
    assert "green" in instruction
    assert "blue" in instruction


def test_a_failed_attempt_explains_itself_and_keeps_the_picture(monkeypatch) -> None:
    def failing(**kwargs):
        raise generators.GeneratorError(
            "OpenAI refused that request.", provider="OpenAI", code="content"
        )

    monkeypatch.setattr(generators, "refine_with_provider", failing)

    at = _result_screen()
    at = _button(at, "colour it in for me").click().run()

    assert not at.exception
    assert at.session_state["showing_colours"] is False
    assert at.session_state["colour_previews"] == {}
    assert at.session_state["quick_processed"] == LINE_ART
