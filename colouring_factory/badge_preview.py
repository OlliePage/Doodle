from __future__ import annotations

from dataclasses import replace

from .models import CalibrationProfile, CircleSheetConfig
from .pdf_export import create_circle_sheet_pdf
from .preview import render_pdf_preview


def render_badge_preview(
    image_bytes: bytes,
    config: CircleSheetConfig,
    calibration: CalibrationProfile | None = None,
    dpi: int = 200,
) -> bytes:
    """Render one badge as a PNG, with all three boundary rings visible.

    Built by exporting a genuine single-badge PDF through the same code path as
    the printed sheet, so what is previewed cannot drift from what is printed.
    The guide checkboxes are overridden on, because showing the boundaries is
    the entire purpose of this view.
    """

    calibration = calibration or CalibrationProfile()
    margin_mm = 4.0

    # Calibration stretches the cut diameter and shifts the grid, so the page
    # must clear the scaled circle plus that shift. Sizing it from the nominal
    # diameter alone makes the badge stop fitting and the preview vanish.
    widest_mm = max(
        config.cut_diameter_mm * calibration.x_scale,
        config.cut_diameter_mm * calibration.y_scale,
        config.finished_diameter_mm,
    )
    offset_mm = max(abs(calibration.x_offset_mm), abs(calibration.y_offset_mm))
    # Sizing the page to exactly the circle puts the fit test on a floating-point
    # knife edge: subtracting the margin back off can land a fraction under the
    # diameter, so nothing fits and the preview vanishes. A tenth of a millimetre
    # of slack is far below print resolution and removes the boundary.
    page_mm = widest_mm + (2.0 * margin_mm) + (2.0 * offset_mm) + 0.1

    single = replace(
        config,
        page_width_mm=page_mm,
        page_height_mm=page_mm,
        margin_mm=margin_mm,
        gap_mm=0.0,
        copies=1,
        show_cut_guide=True,
        show_finished_guide=True,
        show_safe_guide=True,
    )

    pdf_bytes, _count = create_circle_sheet_pdf(image_bytes, single, calibration)
    return render_pdf_preview(pdf_bytes, dpi=dpi)
