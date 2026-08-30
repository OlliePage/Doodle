from io import BytesIO

from PIL import Image, ImageDraw
from pypdf import PdfReader

from colouring_factory.layouts import mm_to_pt, pt_to_mm
from colouring_factory.models import CircleSheetConfig, CustomPageConfig, FullPageConfig
from colouring_factory.pdf_export import (
    create_calibration_pdf,
    create_circle_sheet_pdf,
    create_custom_page_pdf,
    create_full_page_pdf,
)


def _artwork() -> bytes:
    image = Image.new("L", (600, 800), 255)
    draw = ImageDraw.Draw(image)
    draw.ellipse((100, 140, 500, 540), outline=0, width=16)
    draw.arc((200, 260, 400, 440), 10, 170, fill=0, width=12)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _page_mm(pdf_bytes: bytes) -> tuple[float, float]:
    reader = PdfReader(BytesIO(pdf_bytes))
    page = reader.pages[0]
    return pt_to_mm(float(page.mediabox.width)), pt_to_mm(float(page.mediabox.height))


def test_a4_page_box_is_exact() -> None:
    width, height = _page_mm(create_full_page_pdf(_artwork(), FullPageConfig()))
    assert abs(width - 210) < 0.01
    assert abs(height - 297) < 0.01


def test_custom_page_box_is_exact() -> None:
    width, height = _page_mm(
        create_custom_page_pdf(
            _artwork(),
            CustomPageConfig(page_width_mm=83.5, page_height_mm=121.2, margin_mm=4),
        )
    )
    assert abs(width - 83.5) < 0.01
    assert abs(height - 121.2) < 0.01


def test_circle_sheet_and_calibration_are_a4() -> None:
    circle_pdf, count = create_circle_sheet_pdf(_artwork(), CircleSheetConfig())
    assert count == 12
    for data in (circle_pdf, create_calibration_pdf()):
        width, height = _page_mm(data)
        assert abs(width - 210) < 0.01
        assert abs(height - 297) < 0.01


def test_cut_guides_are_exactly_58mm() -> None:
    import fitz

    pdf_bytes, _ = create_circle_sheet_pdf(_artwork(), CircleSheetConfig())
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        drawings = document[0].get_drawings()
    finally:
        document.close()

    assert len(drawings) == 12
    expected = mm_to_pt(58.0)
    for drawing in drawings:
        assert abs(drawing["rect"].width - expected) < 0.02
        assert abs(drawing["rect"].height - expected) < 0.02
