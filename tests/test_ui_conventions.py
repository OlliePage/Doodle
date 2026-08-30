"""Guards for the conventions in docs/ui-conventions.md.

Each of these caught a real inconsistency on 2026-08-30. They exist so the next
control added to Doodle matches the ones already there, rather than inventing a
third name for a setting that already has two.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()

# Typed characters used as makeshift icons. They render at text weight, do not
# match the Material set, and a screen reader announces them as punctuation.
GLYPH_ICONS = "←→↑↓↻↺♡♥✓✗✔✘★☆⌫⏎▶◀"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _studio() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def _layout(name: str) -> AppTest:
    at = _studio()
    for radio in at.radio:
        if radio.label == "Output format":
            return radio.set_value(name).run()
    raise AssertionError("Output format control not found")


def _upload() -> AppTest:
    at = _studio()
    for radio in at.radio:
        if radio.label == "Artwork source":
            return radio.set_value("Upload artwork").run()
    raise AssertionError("Artwork source control not found")


def _result() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.run()
    return at


def _home() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    return at


def _connect() -> AppTest:
    at = _home()
    at.text_input[0].set_value("A bear flying a kite")
    at.button[0].click().run()
    assert at.session_state["screen"] == "connect"
    return at


def _library() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "library"
    at.session_state["library_return"] = "home"
    at.run()
    return at


def _generate() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["quick_mode"] = "demo"
    at.run()
    return at


def _every_screen() -> list[AppTest]:
    """All six screens. A guard that skips one lets a defect through it."""

    return [
        _home(),
        _connect(),
        _result(),
        _studio(),
        _layout("A4 circle sheet"),
        _layout("Custom-size page"),
        _upload(),
        _library(),
        _generate(),
    ]


def _all_labels(at: AppTest) -> list[str]:
    labels: list[str] = []
    for group in (
        at.button,
        at.get("link_button"),
        at.get("download_button"),
        at.text_input,
        at.text_area,
        at.number_input,
        at.selectbox,
        at.radio,
        at.checkbox,
        at.slider,
        at.segmented_control,
        at.get("file_uploader"),
        at.get("toggle"),
        at.get("multiselect"),
    ):
        labels.extend(widget.label for widget in group)
    return [label for label in labels if label]


def test_uploader_and_toggle_labels_are_checked() -> None:
    """The label sweep must see every widget family a screen can hold.

    On 2026-08-30 _all_labels iterated eleven families and missed
    file_uploader, toggle and multiselect, so an uploader's label was
    subject to neither the glyph rule nor the sentence-case rule.
    """

    labels = _all_labels(_upload())
    assert any("upload" in label.lower() for label in labels)


def test_no_control_uses_a_typed_glyph_as_an_icon() -> None:
    offenders = []
    for at in _every_screen():
        offenders += [
            label for label in _all_labels(at) if any(g in label for g in GLYPH_ICONS)
        ]
    assert not offenders, f"use icon=':material/...:' instead of: {offenders}"


def test_the_source_uses_material_icons_rather_than_emoji_on_buttons() -> None:
    source = Path(APP).read_text(encoding="utf-8")
    # The page icon in set_page_config takes no Material Symbol, so it is the
    # one place an emoji is allowed.
    without_page_icon = source.replace('page_icon="✏️"', "")
    emoji = re.findall(r'"[^"\n]*[\U0001F300-\U0001FAFF][^"\n]*"', without_page_icon)
    assert not emoji, f"emoji outside page_icon: {emoji}"


def test_one_label_per_setting_across_the_layout_forms() -> None:
    # Each form used to invent its own wording: "Optional caption on custom
    # page", "Badge caption size (pt)", "Page margin (mm)".
    for name in ("A4 colouring page", "A4 circle sheet", "Custom-size page"):
        labels = _all_labels(_layout(name))
        captions = [label for label in labels if "caption" in label.lower()]
        assert "Caption (optional)" in captions, f"{name}: {captions}"
        assert "Caption size (pt)" in captions, f"{name}: {captions}"


def test_the_margin_around_artwork_has_one_name() -> None:
    for name in ("A4 colouring page", "Custom-size page"):
        margins = [
            label for label in _all_labels(_layout(name)) if "margin" in label.lower()
        ]
        assert "Margin (mm)" in margins, f"{name}: {margins}"

    # The badge sheet's margin surrounds the whole grid, not one picture, so it
    # keeps a different name on purpose.
    circle = [
        label
        for label in _all_labels(_layout("A4 circle sheet"))
        if "margin" in label.lower()
    ]
    assert "Outer margin (mm)" in circle


def test_saving_is_called_the_same_thing_everywhere() -> None:
    studio_buttons = [b.label for b in _studio().button]
    assert "Save to your doodles" in studio_buttons

    result = AppTest.from_file(APP, default_timeout=120)
    result.session_state["screen"] = "result"
    result.session_state["current_raw"] = ARTWORK
    result.session_state["current_title"] = "Test dinosaur"
    result.session_state["current_metadata"] = {"source": "test"}
    result.session_state["quick_processed"] = ARTWORK
    result.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    result.run()
    assert "Save to your doodles" in [b.label for b in result.button]


def test_starting_over_is_called_the_same_thing_everywhere() -> None:
    assert "New doodle" in [b.label for b in _studio().button]

    result = AppTest.from_file(APP, default_timeout=120)
    result.session_state["screen"] = "result"
    result.session_state["current_raw"] = ARTWORK
    result.session_state["current_title"] = "Test dinosaur"
    result.session_state["current_metadata"] = {"source": "test"}
    result.session_state["quick_processed"] = ARTWORK
    result.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    result.run()
    assert "New doodle" in [b.label for b in result.button]


def test_no_button_carries_a_step_number() -> None:
    # "3 · Connect & draw" put the step number inside the button. Numbers belong
    # to the heading above the control.
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    at.text_input[0].set_value("A bear flying a kite")
    at.button[0].click().run()

    assert at.session_state["screen"] == "connect"
    for button in at.button:
        assert not re.match(r"^\s*\d+\s*[·.\-]", button.label), button.label


def test_step_headings_share_one_style() -> None:
    source = Path(APP).read_text(encoding="utf-8")
    headings = re.findall(r'step-label">([^<]+)<', source)
    assert headings, "no step headings found"
    for heading in headings:
        assert re.match(r"^Step \d+ · ", heading), heading


def test_labels_are_sentence_case() -> None:
    # Catches Title Case creeping in. Allows known proper nouns and units.
    allowed = {
        "A4",
        "AI",
        "API",
        "Doodle",
        "Gemini",
        "Google",
        "Mac",
        "OpenAI",
        "PDF",
        "PNG",
        "Recraft",
        "Studio",
        "Enter",
    }
    offenders = []
    for at in _every_screen():
        for label in _all_labels(at):
            words = re.findall(r"[A-Za-z][A-Za-z0-9/]*", label)
            for word in words[1:]:
                if word[0].isupper() and word not in allowed:
                    offenders.append(label)
                    break
    assert not offenders, f"Title Case labels: {sorted(set(offenders))}"
