from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

# A phone photograph carries the camera make, the capture time and, very often,
# the exact coordinates of a family home. None of that belongs in a file handed
# to a third-party image API, so every reference photograph is re-encoded from
# pixels alone before it is stored.
MAX_PHOTO_EDGE_PX = 1536

# Doodle Studio's own "Upload artwork" door takes line art a parent already
# has, such as a scanned A4 page, rather than a reference photo — a 300dpi A4
# scan is already ~2481x3508, well past MAX_PHOTO_EDGE_PX, and clipping it to
# a photo-reference size would visibly degrade something meant to be printed.
# It carries the same GPS/camera/ICC risk whenever the "artwork" happens to be
# a phone photo, so it is worth the same metadata strip; only the size budget
# differs, generous enough that no realistic scan or photo is ever touched.
MAX_ARTWORK_EDGE_PX = 6000

# Photographs straight off an iPhone are HEIC, which Pillow cannot open on its
# own. This is the one runtime dependency the characters feature adds; a photo
# feature that cannot read the format most family photographs are in is broken
# on arrival.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover - only in an incomplete installation.
    # Silent on purpose: everything else about a photograph still works, and a
    # PNG or JPEG must not be refused because a HEIC decoder is missing. The
    # cost of that silence was paid on 2026-08-31, when the package turned out
    # to be absent from the running environment and dropping an iPhone photo
    # failed with nothing on screen explaining why. The cause was the version
    # pin rather than the machine: requirements.txt capped this below 1.0, the
    # newest version under that cap publishes no wheel for Python 3.14, and
    # building it from source needs a libheif that is not installed. Raising
    # the pin to 1.x, which does publish that wheel, fixed it. Keep the pin
    # ahead of the Python this runs on.
    pass


def prepare_photo(photo_bytes: bytes, max_edge: int = MAX_PHOTO_EDGE_PX) -> bytes:
    """Normalise an uploaded reference photograph into a bare PNG.

    Applies the EXIF orientation so a portrait phone photo is not stored on its
    side, discards every metadata block including GPS coordinates, caps the long
    edge so a 48-megapixel original does not become a 60 MB upload, and re-encodes
    as PNG so the "image/png" the generators send is the truth.
    """

    if not photo_bytes:
        raise ValueError("No photograph was supplied.")
    if max_edge < 1:
        raise ValueError("The pixel cap must be at least one pixel.")

    try:
        with Image.open(BytesIO(photo_bytes)) as source:
            source.load()
            # Rotation first: the orientation tag is about to be thrown away with
            # the rest of the metadata, so it has to be baked into the pixels
            # while it is still readable.
            rotated = ImageOps.exif_transpose(source) or source
            flattened = _flatten_to_white(rotated)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("That file could not be read as a photograph.") from exc
    except Image.DecompressionBombError as exc:
        # A crafted header can claim billions of pixels while weighing only a
        # few dozen bytes; Pillow's own guard stops the allocation, but that
        # guard raises a plain Exception, not one of the above, so it has to
        # be turned into the ValueError this function promises its callers.
        raise ValueError(
            "That photograph is too large to process. Please choose a smaller file."
        ) from exc

    if max(flattened.size) > max_edge:
        flattened.thumbnail((max_edge, max_edge), Image.LANCZOS)

    # Copying the pixels into a freshly created image is what actually strips the
    # metadata: Image.new starts with an empty info dictionary, so there is no
    # EXIF block, no ICC profile and no PNG text chunk left for the encoder.
    stripped = Image.new("RGB", flattened.size)
    stripped.paste(flattened)

    output = BytesIO()
    stripped.save(output, format="PNG", optimize=True)
    return output.getvalue()


_HIGH_BIT_DEPTH_MODES = ("I", "I;16", "I;16B", "I;16L", "I;16N")


def _flatten_to_white(image: Image.Image) -> Image.Image:
    # Deliberately duplicated from image_processing._flatten_to_white: that copy
    # serves the colouring-page pipeline and this one serves photo intake, and
    # coupling them would let a change meant for one silently alter the other.
    if image.mode in _HIGH_BIT_DEPTH_MODES:
        # A 16-bit-per-channel greyscale PNG — routine output from a flatbed
        # scanner — opens in one of these modes holding values up to 65535.
        # Image.convert("RGB") on them clips anything above 255 instead of
        # rescaling, so a genuine mid-tone photograph comes out solid white.
        # Dividing down first, while the full range is still there, is what
        # makes the later convert lossless rather than a clip.
        image = image.point(lambda value: value / 257).convert("L")
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")
