import math
from io import BytesIO

import pymupdf
import pytest
from PIL import Image

from colouring_factory.layouts import fit_contain, fit_inscribed, mm_to_pt
from colouring_factory.models import CalibrationProfile, CircleSheetConfig
from colouring_factory.pdf_export import create_circle_sheet_pdf


def _corners(x, y, width, height):
    return ((x, y), (x + width, y), (x, y + height), (x + width, y + height))


def _inside_ellipse(point, centre_x, centre_y, width, height, tolerance=1e-6):
    px, py = point
    normalised = ((px - centre_x) / (width / 2.0)) ** 2 + (
        (py - centre_y) / (height / 2.0)
    ) ** 2
    return normalised <= 1.0 + tolerance


@pytest.mark.parametrize(
    "source_width,source_height",
    [(1024, 1024), (1024, 1536), (1536, 1024), (300, 100)],
)
def test_every_corner_lands_inside_the_circle(source_width, source_height) -> None:
    box = fit_inscribed(source_width, source_height, 100.0, 100.0, 58.0, 58.0)
    for corner in _corners(*box):
        assert _inside_ellipse(corner, 100.0, 100.0, 58.0, 58.0)


def test_a_square_source_uses_the_diameter_over_root_two() -> None:
    _x, _y, width, height = fit_inscribed(1000, 1000, 0.0, 0.0, 58.0, 58.0)
    expected = 58.0 / math.sqrt(2.0)
    assert width == pytest.approx(expected)
    assert height == pytest.approx(expected)


def test_the_aspect_ratio_of_the_source_is_preserved() -> None:
    _x, _y, width, height = fit_inscribed(1024, 1536, 0.0, 0.0, 58.0, 58.0)
    assert width / height == pytest.approx(1024 / 1536)


def test_the_result_is_centred_on_the_given_point() -> None:
    x, y, width, height = fit_inscribed(1024, 1536, 12.0, -7.0, 58.0, 58.0)
    assert x + (width / 2.0) == pytest.approx(12.0)
    assert y + (height / 2.0) == pytest.approx(-7.0)


def test_inscribing_is_smaller_than_containing() -> None:
    _cx, _cy, contain_width, _ch = fit_contain(1000, 1000, 0.0, 0.0, 58.0, 58.0)
    _ix, _iy, inscribe_width, _ih = fit_inscribed(1000, 1000, 29.0, 29.0, 58.0, 58.0)
    assert inscribe_width < contain_width


def test_an_anisotropic_ellipse_is_handled() -> None:
    box = fit_inscribed(1000, 1000, 0.0, 0.0, 60.0, 50.0)
    for corner in _corners(*box):
        assert _inside_ellipse(corner, 0.0, 0.0, 60.0, 50.0)


def test_a_zero_sized_source_is_refused() -> None:
    with pytest.raises(ValueError):
        fit_inscribed(0, 100, 0.0, 0.0, 58.0, 58.0)


def test_a_zero_sized_ellipse_is_refused() -> None:
    with pytest.raises(ValueError):
        fit_inscribed(100, 100, 0.0, 0.0, 0.0, 58.0)


def _full_bleed_png() -> bytes:
    image = Image.new("L", (400, 400), color=255)
    for coordinate in range(400):
        for edge in (0, 1, 398, 399):
            image.putpixel((coordinate, edge), 0)
            image.putpixel((edge, coordinate), 0)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _drawn_width_pt(artwork: bytes, mode: str) -> float:
    config = CircleSheetConfig(copies=1, fit_mode=mode)
    pdf_bytes, _count = create_circle_sheet_pdf(artwork, config, CalibrationProfile())
    page = pymupdf.open(stream=pdf_bytes, filetype="pdf")[0]
    placed = page.get_images(full=True)
    assert placed, "the badge sheet contains no image"
    return page.get_image_rects(placed[0][0])[0].width


def test_inscribe_is_the_default() -> None:
    assert CircleSheetConfig().fit_mode == "inscribe"


def test_inscribed_artwork_is_smaller_than_filled_artwork() -> None:
    artwork = _full_bleed_png()
    assert _drawn_width_pt(artwork, "inscribe") < _drawn_width_pt(artwork, "fill")


def test_inscribed_artwork_measures_the_diameter_over_root_two() -> None:
    # A square source inside the default 50 mm safe circle: 50 / sqrt(2) = 35.36 mm.
    width_pt = _drawn_width_pt(_full_bleed_png(), "inscribe")
    assert width_pt == pytest.approx(mm_to_pt(50.0 / math.sqrt(2.0)), rel=0.01)


def test_fill_mode_reproduces_the_previous_geometry() -> None:
    artwork = _full_bleed_png()
    config = CircleSheetConfig(copies=1, fit_mode="fill")
    pdf_bytes, count = create_circle_sheet_pdf(artwork, config, CalibrationProfile())
    assert count == 1
    assert pdf_bytes.startswith(b"%PDF")
    assert _drawn_width_pt(artwork, "fill") == pytest.approx(mm_to_pt(50.0), rel=0.01)
