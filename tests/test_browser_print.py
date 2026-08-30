"""The block of HTML that reaches the browser's print dialogue.

Verified against a real headless Chrome on 2026-08-30: the script executes,
the PDF loads into the hidden frame as a blob, and print() returns without
throwing. These tests hold the parts of that contract a unit test can see.
"""

from __future__ import annotations

import base64

import pytest

from colouring_factory.browser_print import print_trigger_html

PDF = b"%PDF-1.4\nfake\n%%EOF\n"


def test_the_pdf_travels_inside_the_page() -> None:
    html = print_trigger_html(PDF, nonce="one")
    assert base64.b64encode(PDF).decode("ascii") in html


def test_the_frame_is_asked_to_print_itself() -> None:
    html = print_trigger_html(PDF, nonce="one")
    assert "contentWindow.print()" in html
    assert 'type: "application/pdf"' in html


def test_a_blocked_dialogue_falls_back_to_opening_the_pdf() -> None:
    html = print_trigger_html(PDF, nonce="one")
    assert 'window.open(url, "_blank")' in html


def test_the_nonce_guards_against_printing_again_on_an_unrelated_rerun() -> None:
    html = print_trigger_html(PDF, nonce="seventeen")
    assert html.count("seventeen") >= 2
    assert "window.__doodlePrintNonce" in html


def test_two_requests_produce_different_scripts() -> None:
    assert print_trigger_html(PDF, nonce="one") != print_trigger_html(PDF, nonce="two")


def test_nothing_to_print_is_refused() -> None:
    with pytest.raises(ValueError):
        print_trigger_html(b"", nonce="one")
    with pytest.raises(ValueError):
        print_trigger_html(PDF, nonce="")
