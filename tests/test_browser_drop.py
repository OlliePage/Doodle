"""The whole-page drop target's script, tested as the pure string it is.

AppTest has no DOM, so nothing here can prove a drag reaches Python. What it
can prove is that the script says what it must say, stays identical between
calls, and refuses to carry anything a user typed.
"""

from __future__ import annotations

import json

import pytest

from colouring_factory.browser_drop import (
    DROP_EXTENSIONS,
    DROP_MAX_BYTES,
    drop_overlay_html,
)


def test_the_guard_is_present() -> None:
    """Without it, a payload that ever changes stacks overlays and listeners.

    Measured in headless Chrome on 2026-08-31: four overlays, twelve window
    listeners and one drop handled four times over.
    """

    assert "window.__doodleDrop" in drop_overlay_html()


def test_no_placeholder_survives() -> None:
    html = drop_overlay_html()
    assert "__ACCEPTED__" not in html
    assert "__MAX_BYTES__" not in html


def test_the_accepted_extensions_reach_the_script() -> None:
    html = drop_overlay_html(accepted=("png", "heic"))
    assert json.dumps(["png", "heic"]) in html


def test_heif_is_accepted_by_default() -> None:
    """An iPhone hands over both .heic and .heif, and Streamlit's own filter
    refused live.heif outright when only heic was declared."""

    assert "heif" in DROP_EXTENSIONS
    assert "heif" in drop_overlay_html()


def test_the_size_ceiling_reaches_the_script() -> None:
    assert str(DROP_MAX_BYTES) in drop_overlay_html()
    assert DROP_MAX_BYTES == 200 * 1024 * 1024


def test_a_leading_dot_is_tolerated() -> None:
    assert json.dumps(["png"]) in drop_overlay_html(accepted=(".PNG",))


def test_two_calls_return_the_same_bytes() -> None:
    """Streamlit re-inserts the script whenever the payload changes, so a
    payload that varies between reruns is the bug this test exists to catch."""

    assert drop_overlay_html() == drop_overlay_html()


def test_an_extension_that_is_not_alphanumeric_is_refused() -> None:
    """The one guard standing between this template and script injection."""

    with pytest.raises(ValueError):
        drop_overlay_html(accepted=('png"; alert(1); //',))


def test_an_empty_extension_list_is_refused() -> None:
    with pytest.raises(ValueError):
        drop_overlay_html(accepted=())


def test_a_zero_ceiling_is_refused() -> None:
    with pytest.raises(ValueError):
        drop_overlay_html(max_bytes=0)


def test_the_drop_handler_checks_the_file_before_injecting() -> None:
    """Streamlit's own refusal is written into the hidden block and fires no
    rerun, so a file this script does not check itself reaches the parent as
    silence."""

    html = drop_overlay_html()
    assert "ACCEPTED.indexOf(extensionOf(file.name)) < 0" in html
    assert "file.size > MAX_BYTES" in html


def test_it_prevents_the_browser_taking_the_drop() -> None:
    """Without preventDefault on dragover the browser navigates away to the
    dropped file, losing the app."""

    assert html_count(drop_overlay_html(), "event.preventDefault()") >= 3


def test_it_resolves_the_uploader_at_drop_time() -> None:
    """The script runs before the elements below it have rendered, so a
    reference taken at setup is null for the life of the page."""

    html = drop_overlay_html()
    assert (
        '.st-key-doodle-drop-well input[data-testid="stFileUploaderDropzoneInput"]'
        in html
    )


def test_the_overlay_lives_on_the_body() -> None:
    """st.html clears its own div on unmount; an overlay inside the markup
    would go with it."""

    assert "document.body.appendChild(overlay)" in drop_overlay_html()


def test_it_counts_drag_boundaries() -> None:
    """dragleave fires on every child crossed, so without a depth count the
    panel flickers its way across the page."""

    html = drop_overlay_html()
    assert "depth += 1" in html
    assert "depth -= 1" in html


def html_count(html: str, needle: str) -> int:
    return html.count(needle)
