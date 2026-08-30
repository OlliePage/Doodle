from io import BytesIO

import fitz
from PIL import Image, ImageDraw

from colouring_factory.layouts import compute_circle_sheet_plan, mm_to_pt
from colouring_factory.models import CircleSheetConfig
from colouring_factory.pdf_export import create_circle_sheet_pdf


def _artwork() -> bytes:
    image = Image.new("L", (600, 600), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((110, 80, 490, 460), outline=0, width=22)
    draw.ellipse((210, 190, 245, 225), fill=0)
    draw.ellipse((355, 190, 390, 225), fill=0)
    draw.arc((210, 220, 390, 365), 15, 165, fill=0, width=16)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_every_circle_contains_the_repeated_artwork() -> None:
    config = CircleSheetConfig()
    pdf_bytes, count = create_circle_sheet_pdf(_artwork(), config)
    assert count == 12

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        page = document[0]
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        rendered = Image.open(BytesIO(pixmap.tobytes("png"))).convert("L")
    finally:
        document.close()

    plan = compute_circle_sheet_plan(config)
    scale = 2.0
    inner_mm = config.safe_diameter_mm * 0.78
    inner_px = mm_to_pt(inner_mm) * scale

    for placement in plan.placements:
        centre_x_px = mm_to_pt(placement.centre_x_mm) * scale
        # PDF coordinates start at the bottom; raster coordinates start at the top.
        centre_y_px = rendered.height - (mm_to_pt(placement.centre_y_mm) * scale)
        box = (
            int(centre_x_px - inner_px / 2),
            int(centre_y_px - inner_px / 2),
            int(centre_x_px + inner_px / 2),
            int(centre_y_px + inner_px / 2),
        )
        crop = rendered.crop(box)
        histogram = crop.histogram()
        dark_pixels = sum(histogram[:128])
        assert dark_pixels > 500
