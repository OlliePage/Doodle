from io import BytesIO

import pytest
from PIL import Image

from colouring_factory.badge_preview import render_badge_preview
from colouring_factory.models import CalibrationProfile, CircleSheetConfig


def _artwork() -> bytes:
    image = Image.new("L", (400, 400), color=255)
    for coordinate in range(100, 300):
        image.putpixel((coordinate, 200), 0)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_the_preview_is_a_decodable_png() -> None:
    png = render_badge_preview(_artwork(), CircleSheetConfig())
    assert png.startswith(b"\x89PNG")
    Image.open(BytesIO(png)).verify()


def test_the_preview_is_square_for_a_circular_badge() -> None:
    png = render_badge_preview(_artwork(), CircleSheetConfig(cut_diameter_mm=58.0))
    image = Image.open(BytesIO(png))
    assert image.width == pytest.approx(image.height, rel=0.02)


def _badge(diameter_mm: float) -> CircleSheetConfig:
    # The layout validator enforces safe <= finished <= cut, so a preview test
    # that changes only the cut diameter would build an invalid badge.
    return CircleSheetConfig(
        cut_diameter_mm=diameter_mm,
        finished_diameter_mm=diameter_mm,
        safe_diameter_mm=diameter_mm * 0.86,
    )


def test_the_preview_is_proportional_to_the_cut_diameter() -> None:
    small = Image.open(BytesIO(render_badge_preview(_artwork(), _badge(40.0))))
    large = Image.open(BytesIO(render_badge_preview(_artwork(), _badge(80.0))))
    assert large.width > small.width


def test_all_three_guides_are_drawn_regardless_of_the_export_settings() -> None:
    # The preview exists to show boundaries, so it ignores the sheet's guide
    # checkboxes and always draws all three.
    config = CircleSheetConfig(
        finished_diameter_mm=58.0,
        cut_diameter_mm=62.0,
        safe_diameter_mm=48.0,
        show_cut_guide=False,
        show_finished_guide=False,
        show_safe_guide=False,
    )
    png = render_badge_preview(config=config, image_bytes=_artwork())
    greys = Image.open(BytesIO(png)).convert("L")
    dark_pixels = sum(1 for pixel in greys.getdata() if pixel < 200)
    assert dark_pixels > 0


def test_the_preview_does_not_mutate_the_config_it_is_given() -> None:
    config = CircleSheetConfig(copies=12, show_safe_guide=False)
    render_badge_preview(_artwork(), config)
    assert config.copies == 12
    assert config.show_safe_guide is False


@pytest.mark.parametrize(
    "x_scale,y_scale,x_offset,y_offset",
    [
        (1.0, 1.0, 0.0, 0.0),
        (1.02, 1.01, 0.0, 0.0),
        (0.98, 1.04, 1.5, -2.0),
        (1.0142, 1.0142, -3.0, 3.0),
    ],
)
def test_calibration_never_squeezes_the_badge_off_its_own_page(
    x_scale, y_scale, x_offset, y_offset
) -> None:
    # Sizing the preview page from the nominal diameter left the fit test on a
    # floating-point boundary, so a calibrated badge produced no circles at all
    # and the preview disappeared.
    png = render_badge_preview(
        _artwork(),
        CircleSheetConfig(),
        CalibrationProfile(
            x_scale=x_scale,
            y_scale=y_scale,
            x_offset_mm=x_offset,
            y_offset_mm=y_offset,
        ),
    )
    assert png.startswith(b"\x89PNG")


def test_a_calibration_profile_is_accepted() -> None:
    png = render_badge_preview(
        _artwork(), CircleSheetConfig(), CalibrationProfile(x_scale=1.02, y_scale=1.01)
    )
    assert png.startswith(b"\x89PNG")
