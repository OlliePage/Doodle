from colouring_factory.calibration import profile_from_measurements
from colouring_factory.layouts import compute_circle_sheet_plan, fit_contain
from colouring_factory.models import CalibrationProfile, CircleSheetConfig


def test_58mm_grid_holds_twelve_on_a4() -> None:
    plan = compute_circle_sheet_plan(
        CircleSheetConfig(
            cut_diameter_mm=58,
            finished_diameter_mm=58,
            safe_diameter_mm=50,
            margin_mm=10,
            gap_mm=5,
        )
    )
    assert plan.columns == 3
    assert plan.rows == 4
    assert plan.capacity == 12
    assert len(plan.placements) == 12


def test_copy_limit_is_respected() -> None:
    plan = compute_circle_sheet_plan(CircleSheetConfig(copies=5))
    assert plan.capacity == 12
    assert len(plan.placements) == 5


def test_calibration_expands_encoded_diameter() -> None:
    profile = profile_from_measurements(98.6, 99.0)
    plan = compute_circle_sheet_plan(CircleSheetConfig(), profile)
    assert plan.effective_cut_width_mm > 58
    assert plan.effective_cut_height_mm > 58


def test_fit_contain_centres_source() -> None:
    x, y, width, height = fit_contain(2, 1, 0, 0, 100, 100)
    assert (x, y, width, height) == (0, 25, 100, 50)


def test_invalid_safe_area_is_rejected() -> None:
    config = CircleSheetConfig(
        safe_diameter_mm=60, finished_diameter_mm=58, cut_diameter_mm=58
    )
    try:
        compute_circle_sheet_plan(config, CalibrationProfile())
    except ValueError as exc:
        assert "Safe diameter" in str(exc)
    else:
        raise AssertionError("Expected invalid geometry to raise ValueError")
