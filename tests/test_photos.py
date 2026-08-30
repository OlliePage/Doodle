import struct
import zlib
from io import BytesIO

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from colouring_factory.photos import prepare_photo

# Recognisable stand-in for a real colour profile — an iPhone photo carries a
# genuine Display P3 profile of its own, but the content does not matter here,
# only that it round-trips (or fails to).
ICC_PROFILE = b"FAKE_ICC_PROFILE_MARKER_DOODLE_TEST_1234567890"

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


def _photo_with_icc_profile() -> bytes:
    """A real JPEG carrying an embedded ICC colour profile, as an iPhone's
    Display P3 photos do."""

    image = Image.new("RGB", (60, 40), (180, 90, 40))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", icc_profile=ICC_PROFILE)
    return buffer.getvalue()


def _oversized_header_png() -> bytes:
    """A crafted PNG whose header claims a 50,000 x 50,000 canvas.

    Genuinely allocating a photo that size would need gigabytes, so this
    fixture carries no real pixel data — it exists purely to trip Pillow's
    own decompression-bomb guard at open time, exactly as a hostile upload
    claiming implausible dimensions would.
    """

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data))
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 50000, 50000, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\x00\x00")
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


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


def test_the_icc_fixture_really_carries_a_profile() -> None:
    original = Image.open(BytesIO(_photo_with_icc_profile()))
    assert original.info.get("icc_profile") == ICC_PROFILE


def test_the_icc_profile_does_not_survive_into_the_output() -> None:
    # This guards the rebuild-from-pixels step specifically: converting a
    # JPEG to PNG already drops EXIF for free, so a stripping test that only
    # checks EXIF tags can pass even if that step is deleted. A colour
    # profile is copied across a format change unless something removes it,
    # so it is what actually exercises the rebuild.
    prepared = prepare_photo(_photo_with_icc_profile())
    reopened = Image.open(BytesIO(prepared))

    assert reopened.info.get("icc_profile") is None
    # A PNG carries a colour profile in its own "iCCP" chunk, zlib-compressed,
    # so the profile's plain bytes would not appear in the file even if the
    # profile survived; checking for the chunk tag itself is what a raw-bytes
    # check on this needs to look for.
    assert b"iCCP" not in prepared


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


def test_an_implausibly_large_declared_size_is_refused() -> None:
    # A 68-byte file can declare a 50,000 x 50,000 canvas; Pillow's own guard
    # against decompression bombs stops the allocation, but it raises a plain
    # Exception the caller does not expect, so prepare_photo must translate
    # it into the ValueError its docstring promises.
    with pytest.raises(ValueError):
        prepare_photo(_oversized_header_png())


def test_a_heic_photograph_can_be_read() -> None:
    pillow_heif = pytest.importorskip("pillow_heif")
    source = Image.new("RGB", (120, 80), (200, 30, 40))
    buffer = BytesIO()
    pillow_heif.from_pillow(source).save(buffer, format="HEIF", quality=60)
    prepared = prepare_photo(buffer.getvalue())
    assert Image.open(BytesIO(prepared)).size == (120, 80)
