"""Doodle Studio's own advanced generation form (the "Generate with AI" tab
of Step 1, inside `generation_form`).

Every other paid control was guarded against a queued double-click landing
while its own previous press was still blocked in a network call — this one
sits in top-level script code, not a function, and was left as a named
follow-up (see docs/retros and the stop-a-drawing-in-progress report). It
spends money exactly as the others do, so it needs the same guard.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")


def _one_pixel_png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (1, 1), (180, 90, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _fake_artwork() -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=_one_pixel_png(),
        prompt="a bear flying a kite",
        provider="OpenAI",
        model="gpt-image-2",
    )


def _studio() -> AppTest:
    # "Generate with AI" is the first, default "Artwork source" option, so
    # no radio interaction is needed to reach this form.
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.run()
    return at


def _fill_and_submit(at: AppTest) -> AppTest:
    at.text_area(key="generation_idea").set_value("A bear flying a kite")
    for button in at.button:
        if button.label == "Draw it":
            return button.click().run()
    raise AssertionError("Draw it button not found")


def test_a_queued_double_click_does_not_draw_a_second_time(monkeypatch) -> None:
    calls: list[dict] = []

    def counting_generate(**kwargs):
        calls.append(kwargs)
        return [_fake_artwork()]

    monkeypatch.setattr(generators, "generate_with_provider", counting_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", lambda *a, **k: ["b"])

    at = _studio()
    at.session_state["busy_studio_generate"] = True
    at = _fill_and_submit(at)

    assert not at.exception
    assert calls == []


def test_a_successful_draw_leaves_the_button_pressable_again(monkeypatch) -> None:
    monkeypatch.setattr(
        generators, "generate_with_provider", lambda **kwargs: [_fake_artwork()]
    )
    monkeypatch.setattr(variations, "build_variation_briefs", lambda *a, **k: ["b"])

    at = _studio()
    at = _fill_and_submit(at)

    assert not at.exception
    assert at.session_state["busy_studio_generate"] is False
    assert st_success_shown(at)


def st_success_shown(at: AppTest) -> bool:
    return any("doodles are ready" in str(block.value) for block in at.success)


def test_a_failed_draw_leaves_the_button_pressable_again_not_wedged(
    monkeypatch,
) -> None:
    def failing_generate(**kwargs):
        raise GeneratorError(
            "OpenAI's rate limit was reached.", provider="OpenAI", code="rate_limit"
        )

    monkeypatch.setattr(generators, "generate_with_provider", failing_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", lambda *a, **k: ["b"])

    at = _studio()
    at = _fill_and_submit(at)

    assert not at.exception
    assert at.session_state["busy_studio_generate"] is False
    assert not at.session_state["candidates"]
