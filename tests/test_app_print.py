"""Printing, driven on the real Streamlit runtime.

The print button used to be a download button: it put a PDF in the Downloads
folder and called that printing. Each button here is clicked, and the emitted
HTML is checked for the PDF it is meant to carry.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()
PDF = b"%PDF-1.4\ntest sheet\n%%EOF\n"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _emitted_html(at: AppTest) -> str:
    return " ".join(str(element.proto.body) for element in at.get("html"))


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = PDF
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def test_the_result_screen_prints_rather_than_downloads() -> None:
    at = _result_screen()
    assert not at.exception
    assert not _emitted_html(at).count("doodle-print-frame")

    at = _button(at, "print this doodle").click().run()
    assert not at.exception

    emitted = _emitted_html(at)
    assert "doodle-print-frame" in emitted
    assert "contentWindow.print()" in emitted
    assert base64.b64encode(PDF).decode("ascii") in emitted


def test_the_scale_warning_is_next_to_the_print_button() -> None:
    at = _result_screen()
    captions = " ".join(caption.value for caption in at.caption)
    assert "100%" in captions
    assert "Fit to page" in captions


def test_the_pdf_is_still_downloadable_when_a_browser_blocks_printing() -> None:
    at = _result_screen()
    labels = [button.label for button in at.download_button]
    assert "Download the PDF" in labels


def test_printing_twice_asks_the_browser_twice() -> None:
    at = _result_screen()
    at = _button(at, "print this doodle").click().run()
    first = at.session_state["print_nonce"]

    at = _button(at, "print this doodle").click().run()
    assert at.session_state["print_nonce"] == first + 1
    assert f"doodle-print-{first + 1}" in _emitted_html(at)


def test_the_studio_prints_the_layout_it_built() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()

    at = _button(at, "build print-ready pdf").click().run()
    assert not at.exception
    assert at.session_state["pdf_bytes"]

    at = _button(at, "print this layout").click().run()
    assert not at.exception
    emitted = _emitted_html(at)
    assert "doodle-print-frame" in emitted
    assert base64.b64encode(at.session_state["pdf_bytes"]).decode("ascii") in emitted


def test_the_calibration_page_prints_too() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.run()

    at = _button(at, "print the calibration page").click().run()
    assert not at.exception
    assert "doodle-print-frame" in _emitted_html(at)


def test_a_finished_doodle_offers_both_printing_and_the_file() -> None:
    """Saving the PDF used to live inside the "Nothing happened when I pressed
    print" panel, as the consolation prize for a browser that refused a print
    dialogue. Wanting the file is as ordinary as wanting the printer — to print
    it elsewhere, keep it, or send it to somebody."""

    at = _result_screen()
    assert not at.exception

    labels = [button.label for button in at.button]
    assert "Print this doodle" in labels

    downloads = [button.label for button in at.get("download_button")]
    assert "Save as a PDF" in downloads, (
        "the only way to get the file is still buried in the print-trouble panel"
    )
