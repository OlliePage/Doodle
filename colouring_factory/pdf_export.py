from __future__ import annotations

from io import BytesIO

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .layouts import compute_circle_sheet_plan, fit_contain, mm_to_pt
from .models import (
    CalibrationProfile,
    CircleSheetConfig,
    CustomPageConfig,
    FullPageConfig,
)


def _image_dimensions(image_bytes: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(image_bytes)) as image:
        return image.width, image.height


def _draw_image_contain(
    pdf: canvas.Canvas,
    image_bytes: bytes,
    x_pt: float,
    y_pt: float,
    width_pt: float,
    height_pt: float,
) -> None:
    source_w, source_h = _image_dimensions(image_bytes)
    x, y, width, height = fit_contain(
        source_w,
        source_h,
        x_pt,
        y_pt,
        width_pt,
        height_pt,
    )
    pdf.drawImage(
        ImageReader(BytesIO(image_bytes)),
        x,
        y,
        width=width,
        height=height,
        preserveAspectRatio=True,
        anchor="c",
        mask="auto",
    )


def _wrap_text(text: str, font_name: str, font_size: float, max_width_pt: float) -> list[str]:
    words = text.split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font_name, font_size) <= max_width_pt:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _draw_centred_caption(
    pdf: canvas.Canvas,
    text: str,
    centre_x_pt: float,
    centre_y_pt: float,
    max_width_pt: float,
    max_height_pt: float,
    preferred_font_size: float,
    font_name: str = "Helvetica-Bold",
    max_lines: int = 3,
) -> None:
    text = text.strip()
    if not text or max_height_pt <= 0:
        return

    font_size = preferred_font_size
    lines: list[str] = []
    while font_size >= 5.0:
        lines = _wrap_text(text, font_name, font_size, max_width_pt)
        leading = font_size * 1.2
        if len(lines) <= max_lines and (len(lines) * leading) <= max_height_pt:
            break
        font_size -= 0.5

    if not lines:
        return

    leading = font_size * 1.2
    block_height = len(lines) * leading
    baseline = centre_y_pt + (block_height / 2.0) - leading + (font_size * 0.15)
    pdf.setFont(font_name, font_size)
    pdf.setFillColor(colors.black)
    for index, line in enumerate(lines[:max_lines]):
        pdf.drawCentredString(centre_x_pt, baseline - (index * leading), line)


def _new_canvas(buffer: BytesIO, page_width_mm: float, page_height_mm: float, title: str) -> canvas.Canvas:
    pdf = canvas.Canvas(
        buffer,
        pagesize=(mm_to_pt(page_width_mm), mm_to_pt(page_height_mm)),
        pageCompression=1,
    )
    pdf.setTitle(title)
    pdf.setAuthor("Doodle")
    pdf.setSubject("Print-ready colouring artwork with deterministic dimensions")
    return pdf


def create_full_page_pdf(image_bytes: bytes, config: FullPageConfig) -> bytes:
    if config.page_width_mm <= 0 or config.page_height_mm <= 0:
        raise ValueError("Page dimensions must be positive.")
    if (2 * config.margin_mm) >= min(config.page_width_mm, config.page_height_mm):
        raise ValueError("The margin is too large for the selected page.")

    buffer = BytesIO()
    pdf = _new_canvas(buffer, config.page_width_mm, config.page_height_mm, "Colouring page")

    page_w = mm_to_pt(config.page_width_mm)
    page_h = mm_to_pt(config.page_height_mm)
    margin = mm_to_pt(config.margin_mm)
    caption_height = mm_to_pt(config.caption_area_mm) if config.caption.strip() else 0.0

    art_x = margin
    art_y = margin + caption_height
    art_w = page_w - (2.0 * margin)
    art_h = page_h - (2.0 * margin) - caption_height
    if art_h <= 0:
        raise ValueError("The caption area leaves no room for artwork.")

    _draw_image_contain(pdf, image_bytes, art_x, art_y, art_w, art_h)

    if config.caption.strip():
        _draw_centred_caption(
            pdf,
            config.caption,
            page_w / 2.0,
            margin + (caption_height / 2.0),
            art_w,
            caption_height * 0.85,
            config.caption_font_size_pt,
        )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def create_custom_page_pdf(image_bytes: bytes, config: CustomPageConfig) -> bytes:
    full_config = FullPageConfig(
        page_width_mm=config.page_width_mm,
        page_height_mm=config.page_height_mm,
        margin_mm=config.margin_mm,
        caption=config.caption,
        caption_font_size_pt=config.caption_font_size_pt,
        caption_area_mm=config.caption_area_mm,
    )
    return create_full_page_pdf(image_bytes, full_config)


def create_circle_sheet_pdf(
    image_bytes: bytes,
    config: CircleSheetConfig,
    calibration: CalibrationProfile | None = None,
) -> tuple[bytes, int]:
    calibration = calibration or CalibrationProfile()
    plan = compute_circle_sheet_plan(config, calibration)
    if not plan.placements:
        raise ValueError("No circles fit on the selected page with these dimensions.")

    buffer = BytesIO()
    pdf = _new_canvas(buffer, config.page_width_mm, config.page_height_mm, "Circular colouring sheet")

    safe_w_mm = config.safe_diameter_mm * calibration.x_scale
    safe_h_mm = config.safe_diameter_mm * calibration.y_scale
    finished_w_mm = config.finished_diameter_mm * calibration.x_scale
    finished_h_mm = config.finished_diameter_mm * calibration.y_scale

    for placement in plan.placements:
        centre_x = mm_to_pt(placement.centre_x_mm)
        centre_y = mm_to_pt(placement.centre_y_mm)
        cut_w = mm_to_pt(placement.cut_width_mm)
        cut_h = mm_to_pt(placement.cut_height_mm)
        safe_w = mm_to_pt(safe_w_mm)
        safe_h = mm_to_pt(safe_h_mm)
        finished_w = mm_to_pt(finished_w_mm)
        finished_h = mm_to_pt(finished_h_mm)

        # Artwork is clipped to the safe circle/ellipse. An anisotropic PDF
        # ellipse may be intentional when compensating for printer distortion.
        pdf.saveState()
        clip = pdf.beginPath()
        # PDFPathObject.ellipse uses x, y, width, height (unlike
        # canvas.ellipse, which uses two corner coordinates).
        clip.ellipse(
            centre_x - (safe_w / 2.0),
            centre_y - (safe_h / 2.0),
            safe_w,
            safe_h,
        )
        pdf.clipPath(clip, stroke=0, fill=0)

        if config.caption.strip():
            caption_h = safe_h * 0.24
            art_h = safe_h - caption_h
            _draw_image_contain(
                pdf,
                image_bytes,
                centre_x - (safe_w / 2.0),
                centre_y - (safe_h / 2.0) + caption_h,
                safe_w,
                art_h,
            )
            _draw_centred_caption(
                pdf,
                config.caption,
                centre_x,
                centre_y - (safe_h / 2.0) + (caption_h / 2.0),
                safe_w * 0.80,
                caption_h * 0.75,
                config.caption_font_size_pt,
                max_lines=2,
            )
        else:
            _draw_image_contain(
                pdf,
                image_bytes,
                centre_x - (safe_w / 2.0),
                centre_y - (safe_h / 2.0),
                safe_w,
                safe_h,
            )
        pdf.restoreState()

        pdf.setFillColor(colors.black)
        pdf.setStrokeColor(colors.black)

        if config.show_cut_guide:
            pdf.setLineWidth(0.45)
            pdf.setDash()
            pdf.ellipse(
                centre_x - (cut_w / 2.0),
                centre_y - (cut_h / 2.0),
                centre_x + (cut_w / 2.0),
                centre_y + (cut_h / 2.0),
                stroke=1,
                fill=0,
            )

        if config.show_finished_guide and (
            abs(config.finished_diameter_mm - config.cut_diameter_mm) > 0.01
        ):
            pdf.setStrokeColor(colors.Color(0.45, 0.45, 0.45))
            pdf.setLineWidth(0.35)
            pdf.setDash(2, 2)
            pdf.ellipse(
                centre_x - (finished_w / 2.0),
                centre_y - (finished_h / 2.0),
                centre_x + (finished_w / 2.0),
                centre_y + (finished_h / 2.0),
                stroke=1,
                fill=0,
            )

        if config.show_safe_guide:
            pdf.setStrokeColor(colors.Color(0.68, 0.68, 0.68))
            pdf.setLineWidth(0.3)
            pdf.setDash(1, 2)
            pdf.ellipse(
                centre_x - (safe_w / 2.0),
                centre_y - (safe_h / 2.0),
                centre_x + (safe_w / 2.0),
                centre_y + (safe_h / 2.0),
                stroke=1,
                fill=0,
            )

    pdf.showPage()
    pdf.save()
    return buffer.getvalue(), len(plan.placements)


def create_calibration_pdf() -> bytes:
    """Create an uncompensated A4 page for measuring printer scaling."""

    page_width_mm = 210.0
    page_height_mm = 297.0
    buffer = BytesIO()
    pdf = _new_canvas(buffer, page_width_mm, page_height_mm, "Printer calibration")

    page_w = mm_to_pt(page_width_mm)
    page_h = mm_to_pt(page_height_mm)
    pdf.setStrokeColor(colors.black)
    pdf.setFillColor(colors.black)

    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(mm_to_pt(18), page_h - mm_to_pt(22), "Doodle printer calibration")
    pdf.setFont("Helvetica", 10)
    instruction = (
        "Print at Actual size / 100%. Disable Fit, Shrink and Scale to printable area. "
        "Measure the lines between the outer faces of the end ticks."
    )
    lines = _wrap_text(instruction, "Helvetica", 10, page_w - mm_to_pt(36))
    y = page_h - mm_to_pt(31)
    for line in lines:
        pdf.drawString(mm_to_pt(18), y, line)
        y -= 13

    # 100 mm horizontal line.
    x0 = mm_to_pt(25)
    y0 = page_h - mm_to_pt(70)
    length = mm_to_pt(100)
    tick = mm_to_pt(4)
    pdf.setLineWidth(1.0)
    pdf.line(x0, y0, x0 + length, y0)
    pdf.line(x0, y0 - tick, x0, y0 + tick)
    pdf.line(x0 + length, y0 - tick, x0 + length, y0 + tick)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(x0 + (length / 2), y0 + mm_to_pt(5), "100 mm horizontal")

    # 100 mm vertical line.
    vx = mm_to_pt(35)
    vy = page_h - mm_to_pt(205)
    pdf.line(vx, vy, vx, vy + length)
    pdf.line(vx - tick, vy, vx + tick, vy)
    pdf.line(vx - tick, vy + length, vx + tick, vy + length)
    pdf.saveState()
    pdf.translate(vx - mm_to_pt(7), vy + (length / 2))
    pdf.rotate(90)
    pdf.drawCentredString(0, 0, "100 mm vertical")
    pdf.restoreState()

    # 58 mm circle and 20 mm square.
    circle_cx = mm_to_pt(150)
    circle_cy = page_h - mm_to_pt(125)
    diameter = mm_to_pt(58)
    pdf.circle(circle_cx, circle_cy, diameter / 2.0, stroke=1, fill=0)
    pdf.drawCentredString(circle_cx, circle_cy + (diameter / 2.0) + mm_to_pt(5), "58 mm circle")

    square_x = mm_to_pt(125)
    square_y = page_h - mm_to_pt(225)
    square = mm_to_pt(20)
    pdf.rect(square_x, square_y, square, square, stroke=1, fill=0)
    pdf.drawString(square_x + square + mm_to_pt(5), square_y + mm_to_pt(7), "20 mm square")

    pdf.setFont("Helvetica", 9)
    footer = (
        "Enter the measured horizontal and vertical 100 mm lengths in the app. "
        "The resulting profile compensates future circular badge-sheet output."
    )
    footer_lines = _wrap_text(footer, "Helvetica", 9, page_w - mm_to_pt(36))
    fy = mm_to_pt(25)
    for line in footer_lines:
        pdf.drawString(mm_to_pt(18), fy, line)
        fy -= 11

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
