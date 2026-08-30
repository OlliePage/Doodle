from io import BytesIO

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from colouring_factory.photos import prepare_photo

# 51°30'N, 0°7'W — the coordinates a London phone photo would carry. Pillow 12
# encodes a RATIONAL from an IFDRational, not from a (numerator, denominator)
# tuple, so the fixture builds them explicitly.
GPS_LATITUDE = (IFDRational(51), IFDRational(30), IFDRational(0))
GPS_LONGITUDE = (IFDRational(0), IFDRational(7), IFDRational(0))

ORIENTATION = 0x0112
MAKE = 0x010F
GPS_IFD_POINTER = 0x8825


def _photo_with_gps(size=(60, 40), orientation=6) -> bytes:
    """A real JPEG carrying a populated GPS IFD, a Make tag and an orientation."""

    image = Image.new("RGB", size, (180, 90, 40))
    exif = Image.Exif()
    exif[MAKE] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[ORIENTATION] = orientation
    exif[GPS_IFD_POINTER] = {
        0: b"\x02\x03\x00\x00",
        1: "N",
        2: GPS_LATITUDE,
        3: "W",
        4: GPS_LONGITUDE,
        5: 0,
        6: IFDRational(12),
    }
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_the_fixture_really_carries_gps_and_a_make_tag() -> None:
    original = Image.open(BytesIO(_photo_with_gps()))
    exif = original.getexif()
    assert exif[MAKE] == "Apple"
    assert exif[ORIENTATION] == 6
    gps = exif.get_ifd(GPS_IFD_POINTER)
    assert gps[2] == GPS_LATITUDE
    assert b"Apple" in _photo_with_gps()


def test_gps_and_every_other_exif_tag_are_gone() -> None:
    prepared = prepare_photo(_photo_with_gps())
    reopened = Image.open(BytesIO(prepared))

    assert dict(reopened.getexif()) == {}
    assert reopened.getexif().get_ifd(GPS_IFD_POINTER) == {}
    assert "exif" not in reopened.info
    assert reopened.info.get("icc_profile") is None
    # Belt and braces against a tag surviving in a chunk getexif does not read.
    assert b"Apple" not in prepared
    assert b"GPS" not in prepared


def test_the_output_really_is_a_png() -> None:
    assert Image.open(BytesIO(prepare_photo(_photo_with_gps()))).format == "PNG"


def test_orientation_six_is_baked_into_the_pixels() -> None:
    # A 60x40 landscape original with orientation 6 is a portrait photograph
    # held sideways, so the stored pixels must come back 40x60.
    prepared = prepare_photo(_photo_with_gps(size=(60, 40), orientation=6))
    assert Image.open(BytesIO(prepared)).size == (40, 60)


def test_a_large_photo_is_capped_on_its_long_edge() -> None:
    big = Image.new("RGB", (4000, 3000), "red")
    buffer = BytesIO()
    big.save(buffer, format="JPEG")
    assert Image.open(BytesIO(prepare_photo(buffer.getvalue()))).size == (1536, 1152)


def test_a_small_photo_is_not_upscaled() -> None:
    small = Image.new("RGB", (80, 60), "red")
    buffer = BytesIO()
    small.save(buffer, format="PNG")
    assert Image.open(BytesIO(prepare_photo(buffer.getvalue()))).size == (80, 60)


def test_transparency_is_flattened_onto_white() -> None:
    transparent = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    buffer = BytesIO()
    transparent.save(buffer, format="PNG")
    flattened = Image.open(BytesIO(prepare_photo(buffer.getvalue())))
    assert flattened.mode == "RGB"
    assert flattened.getpixel((5, 5)) == (255, 255, 255)


def test_empty_and_unreadable_input_are_refused() -> None:
    with pytest.raises(ValueError):
        prepare_photo(b"")
    with pytest.raises(ValueError):
        prepare_photo(b"this is not a picture")


def test_a_heic_photograph_can_be_read() -> None:
    pillow_heif = pytest.importorskip("pillow_heif")
    source = Image.new("RGB", (120, 80), (200, 30, 40))
    buffer = BytesIO()
    pillow_heif.from_pillow(source).save(buffer, format="HEIF", quality=60)
    prepared = prepare_photo(buffer.getvalue())
    assert Image.open(BytesIO(prepared)).size == (120, 80)
