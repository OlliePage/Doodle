from __future__ import annotations

from .models import CalibrationProfile


def profile_from_measurements(
    measured_horizontal_mm: float,
    measured_vertical_mm: float,
    expected_mm: float = 100.0,
    x_offset_mm: float = 0.0,
    y_offset_mm: float = 0.0,
) -> CalibrationProfile:
    if measured_horizontal_mm <= 0 or measured_vertical_mm <= 0:
        raise ValueError("Measured lengths must be greater than zero.")
    if expected_mm <= 0:
        raise ValueError("Expected length must be greater than zero.")
    return CalibrationProfile(
        x_scale=expected_mm / measured_horizontal_mm,
        y_scale=expected_mm / measured_vertical_mm,
        x_offset_mm=x_offset_mm,
        y_offset_mm=y_offset_mm,
    )
