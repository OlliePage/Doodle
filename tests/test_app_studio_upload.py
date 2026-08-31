"""Doodle Studio's own "Upload artwork" door must strip what the
characters door already strips from an identical file.

SEC-03 (audit-security-characters.md): a photograph uploaded here keeps its
GPS, camera make, capture time and original filename, and is written
verbatim into ~/.doodle/library/<id>/raw.png — a JPEG under a .png name.
The characters door runs every upload through prepare_photo(); this one
wrote uploaded.getvalue() straight to session state with no preparation at
all.
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from tests.test_photos import GPS_IFD_POINTER, _photo_with_gps

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)


def _upload_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["screen"] = "studio"
    at.run()
    for radio in at.radio:
        if radio.label == "Artwork source":
            radio.set_value("Upload artwork").run()
            break
    else:
        raise AssertionError("Artwork source control not found")
    return at


def _click_use_uploaded_artwork(at: AppTest) -> AppTest:
    for button in at.button:
        if button.label == "Use uploaded artwork":
            return button.click().run()
    raise AssertionError("Use uploaded artwork button not found")


def test_uploaded_artwork_has_its_gps_and_camera_data_stripped() -> None:
    at = _upload_screen()
    at.get("file_uploader")[0].set_value(
        ("ida_birthday.jpg", _photo_with_gps(), "image/jpeg")
    ).run()
    at = _click_use_uploaded_artwork(at)

    assert not at.exception
    stored = at.session_state["current_raw"]
    reopened = Image.open(BytesIO(stored))
    assert dict(reopened.getexif()) == {}
    assert reopened.getexif().get_ifd(GPS_IFD_POINTER) == {}
    assert b"Apple" not in stored
    assert b"GPS" not in stored


def test_uploaded_artwork_metadata_does_not_carry_the_original_filename() -> None:
    at = _upload_screen()
    at.get("file_uploader")[0].set_value(
        ("ida_birthday.jpg", _photo_with_gps(), "image/jpeg")
    ).run()
    at = _click_use_uploaded_artwork(at)

    assert "original_filename" not in at.session_state["current_metadata"]


def test_an_unreadable_upload_is_refused_with_an_error_not_a_crash() -> None:
    at = _upload_screen()
    at.get("file_uploader")[0].set_value(
        ("notes.jpg", b"this is not a picture", "image/jpeg")
    ).run()
    at = _click_use_uploaded_artwork(at)

    assert not at.exception
    assert at.error
    assert not at.session_state["current_raw"]


def test_a_high_resolution_scan_is_not_downsized_to_photo_reference_size() -> None:
    # prepare_photo's default 1536px cap is tuned for an AI-provider reference
    # photo; a scanned A4 line-art page at 300dpi is ~2481x3508 and must not
    # be visibly degraded just because the same stripping function is reused.
    big = Image.new("RGB", (2481, 3508), "white")
    buffer = BytesIO()
    big.save(buffer, format="PNG")

    at = _upload_screen()
    at.get("file_uploader")[0].set_value(
        ("scan.png", buffer.getvalue(), "image/png")
    ).run()
    at = _click_use_uploaded_artwork(at)

    assert not at.exception
    stored = Image.open(BytesIO(at.session_state["current_raw"]))
    assert stored.size == (2481, 3508)
