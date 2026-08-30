from __future__ import annotations

import math

from .models import (
    CalibrationProfile,
    CirclePlacement,
    CircleSheetConfig,
    CircleSheetPlan,
)

MM_TO_PT = 72.0 / 25.4


def mm_to_pt(value_mm: float) -> float:
    return float(value_mm) * MM_TO_PT


def pt_to_mm(value_pt: float) -> float:
    return float(value_pt) / MM_TO_PT


def fit_contain(
    source_width: float,
    source_height: float,
    box_x: float,
    box_y: float,
    box_width: float,
    box_height: float,
) -> tuple[float, float, float, float]:
    if source_width <= 0 or source_height <= 0:
        raise ValueError("Source dimensions must be positive.")
    if box_width <= 0 or box_height <= 0:
        raise ValueError("Target box dimensions must be positive.")

    scale = min(box_width / source_width, box_height / source_height)
    width = source_width * scale
    height = source_height * scale
    x = box_x + ((box_width - width) / 2.0)
    y = box_y + ((box_height - height) / 2.0)
    return x, y, width, height


def largest_margin_that_fits(
    config: CircleSheetConfig,
    calibration: CalibrationProfile | None = None,
) -> float | None:
    """The largest half-millimetre margin leaving room for at least one circle.

    Takes the same calibration the layout will use. Measuring the nominal
    diameter instead would suggest a margin that still does not fit whenever
    printer compensation is applied, so the offered fix would change nothing.

    Returns None when the badge itself is as wide as the page, where no margin
    can help and the diameter has to change instead.
    """

    calibration = calibration or CalibrationProfile()
    # The grid is laid out from the scaled diameter, and the wider of the two
    # axes is what actually has to fit on the shorter side of the page.
    scaled_diameter = config.cut_diameter_mm * max(
        calibration.x_scale, calibration.y_scale
    )

    smallest_page = min(config.page_width_mm, config.page_height_mm)
    if scaled_diameter >= smallest_page:
        return None

    usable = (smallest_page - scaled_diameter) / 2.0
    return max(0.0, math.floor(usable * 2.0) / 2.0)


def fit_inscribed(
    source_width: float,
    source_height: float,
    centre_x: float,
    centre_y: float,
    ellipse_width: float,
    ellipse_height: float,
    offset_y: float = 0.0,
) -> tuple[float, float, float, float]:
    """Largest rectangle of the source's aspect ratio fitting wholly inside the ellipse.

    Scaling a rectangle to the ellipse's bounding box leaves its corners outside
    the ellipse, so anything drawn there is clipped away. Solving the ellipse
    equation for the worst corner instead guarantees nothing is lost.

    `offset_y` shifts the rectangle's centre away from the ellipse's, which a
    caption requires: the artwork moves up to clear the text, and its lower
    corners then swing further from the centre. Solving against the shifted
    corner is what keeps them inside. With half-extents (a, b), aspect ratio
    r = w/h and shift d, the binding corner is (w/2, |d| + h/2), giving

        (r·h / 2a)² + ((|d| + h/2) / b)² = 1

    a quadratic in h. At d = 0 it reduces to w = 2abr / sqrt(r²b² + a²).
    """

    if source_width <= 0 or source_height <= 0:
        raise ValueError("Source dimensions must be positive.")
    if ellipse_width <= 0 or ellipse_height <= 0:
        raise ValueError("Ellipse dimensions must be positive.")

    semi_x = ellipse_width / 2.0
    semi_y = ellipse_height / 2.0
    ratio = source_width / source_height
    shift = abs(offset_y)

    if shift >= semi_y:
        raise ValueError("The offset places the artwork outside the ellipse.")

    quadratic_a = ((ratio / (2.0 * semi_x)) ** 2) + (1.0 / (4.0 * (semi_y**2)))
    quadratic_b = shift / (semi_y**2)
    quadratic_c = ((shift**2) / (semi_y**2)) - 1.0

    discriminant = (quadratic_b**2) - (4.0 * quadratic_a * quadratic_c)
    height = (-quadratic_b + math.sqrt(discriminant)) / (2.0 * quadratic_a)
    width = height * ratio

    rectangle_centre_y = centre_y + offset_y
    return (
        centre_x - (width / 2.0),
        rectangle_centre_y - (height / 2.0),
        width,
        height,
    )


def validate_circle_config(config: CircleSheetConfig) -> None:
    positive_values = {
        "page width": config.page_width_mm,
        "page height": config.page_height_mm,
        "finished diameter": config.finished_diameter_mm,
        "cut diameter": config.cut_diameter_mm,
        "safe diameter": config.safe_diameter_mm,
    }
    for label, value in positive_values.items():
        if value <= 0:
            raise ValueError(f"{label.title()} must be greater than zero.")

    if config.safe_diameter_mm > config.finished_diameter_mm:
        raise ValueError("Safe diameter cannot exceed finished diameter.")
    if config.finished_diameter_mm > config.cut_diameter_mm:
        raise ValueError("Finished diameter cannot exceed cut diameter.")
    if config.margin_mm < 0 or config.gap_mm < 0:
        raise ValueError("Margins and gaps cannot be negative.")


def compute_circle_sheet_plan(
    config: CircleSheetConfig,
    calibration: CalibrationProfile | None = None,
) -> CircleSheetPlan:
    validate_circle_config(config)
    calibration = calibration or CalibrationProfile()

    cut_w = config.cut_diameter_mm * calibration.x_scale
    cut_h = config.cut_diameter_mm * calibration.y_scale
    gap_x = config.gap_mm * calibration.x_scale
    gap_y = config.gap_mm * calibration.y_scale
    margin_x = config.margin_mm
    margin_y = config.margin_mm

    available_w = config.page_width_mm - (2.0 * margin_x)
    available_h = config.page_height_mm - (2.0 * margin_y)
    columns = math.floor((available_w + gap_x) / (cut_w + gap_x))
    rows = math.floor((available_h + gap_y) / (cut_h + gap_y))

    if columns < 1 or rows < 1:
        return CircleSheetPlan(
            columns=max(0, columns),
            rows=max(0, rows),
            capacity=0,
            placements=(),
            effective_cut_width_mm=cut_w,
            effective_cut_height_mm=cut_h,
        )

    capacity = columns * rows
    requested = capacity if config.copies <= 0 else min(config.copies, capacity)

    grid_w = (columns * cut_w) + ((columns - 1) * gap_x)
    grid_h = (rows * cut_h) + ((rows - 1) * gap_y)
    start_x = ((config.page_width_mm - grid_w) / 2.0) + calibration.x_offset_mm
    start_y = ((config.page_height_mm - grid_h) / 2.0) + calibration.y_offset_mm

    placements: list[CirclePlacement] = []
    for row in range(rows):
        for column in range(columns):
            if len(placements) >= requested:
                break
            centre_x = start_x + (cut_w / 2.0) + (column * (cut_w + gap_x))
            # Place rows from the top down, which matches the visual order in the UI.
            centre_y = (
                config.page_height_mm
                - start_y
                - (cut_h / 2.0)
                - (row * (cut_h + gap_y))
            )
            placements.append(
                CirclePlacement(
                    centre_x_mm=centre_x,
                    centre_y_mm=centre_y,
                    cut_width_mm=cut_w,
                    cut_height_mm=cut_h,
                )
            )

    return CircleSheetPlan(
        columns=columns,
        rows=rows,
        capacity=capacity,
        placements=tuple(placements),
        effective_cut_width_mm=cut_w,
        effective_cut_height_mm=cut_h,
    )
