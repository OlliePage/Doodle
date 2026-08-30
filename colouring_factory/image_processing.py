from __future__ import annotations

from io import BytesIO
from typing import Any

from PIL import Image, ImageFilter, ImageOps, ImageStat

from .models import ProcessingOptions


def _flatten_to_white(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")


def _should_invert(gray: Image.Image) -> bool:
    sample = gray.copy()
    sample.thumbnail((64, 64))
    mean = ImageStat.Stat(sample).mean[0]
    # A normal colouring page is overwhelmingly light. This catches scans or
    # generated images with a dark background without inverting ordinary art.
    return mean < 105


def _crop_content(binary: Image.Image, padding_percent: float) -> Image.Image:
    ink_mask = ImageOps.invert(binary)
    bbox = ink_mask.getbbox()
    if not bbox:
        return binary

    left, top, right, bottom = bbox
    content_w = max(1, right - left)
    content_h = max(1, bottom - top)
    pad = int(round(max(content_w, content_h) * max(0.0, padding_percent) / 100.0))

    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(binary.width, right + pad)
    bottom = min(binary.height, bottom + pad)
    return binary.crop((left, top, right, bottom))


def normalise_line_art(image_bytes: bytes, options: ProcessingOptions) -> bytes:
    """Convert arbitrary artwork into a clean, binary, print-friendly PNG."""

    if not image_bytes:
        raise ValueError("No image data supplied.")

    with Image.open(BytesIO(image_bytes)) as source:
        image = _flatten_to_white(source)

    gray = ImageOps.grayscale(image)

    if options.despeckle_size in (3, 5):
        gray = gray.filter(ImageFilter.MedianFilter(options.despeckle_size))

    gray = ImageOps.autocontrast(gray, cutoff=1)
    if options.auto_invert and _should_invert(gray):
        gray = ImageOps.invert(gray)

    threshold = max(0, min(255, int(options.threshold)))
    binary = gray.point(lambda value: 255 if value >= threshold else 0, mode="L")

    if options.thicken_pixels > 0:
        kernel = min(9, 1 + (2 * int(options.thicken_pixels)))
        if kernel % 2 == 0:
            kernel += 1
        binary = binary.filter(ImageFilter.MinFilter(kernel))

    if options.crop_whitespace:
        binary = _crop_content(binary, options.padding_percent)

    output = BytesIO()
    binary.save(output, format="PNG", optimize=True)
    return output.getvalue()


def analyse_line_art(image_bytes: bytes) -> dict[str, Any]:
    with Image.open(BytesIO(image_bytes)) as image:
        gray = image.convert("L")
        histogram = gray.histogram()
        total = max(1, image.width * image.height)
        blackish = sum(histogram[:128])
        return {
            "width_px": image.width,
            "height_px": image.height,
            "ink_percent": round((blackish / total) * 100.0, 2),
            "mode": image.mode,
        }
