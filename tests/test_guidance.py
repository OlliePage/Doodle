import inspect
import re

from colouring_factory import generators, variations
from colouring_factory.guidance import GUIDANCE_CODES, Guidance, guidance_for
from colouring_factory.layouts import (
    compute_circle_sheet_plan,
    largest_margin_that_fits,
)
from colouring_factory.models import CalibrationProfile, CircleSheetConfig


def _codes_raised_in(module) -> set[str]:
    return set(re.findall(r'code="([a-z_]+)"', inspect.getsource(module)))


def test_every_generator_error_code_has_guidance() -> None:
    raised = _codes_raised_in(generators)
    assert raised, "no error codes found in generators.py"
    missing = raised - GUIDANCE_CODES
    assert not missing, f"no guidance for: {sorted(missing)}"


def test_every_variation_error_code_has_guidance() -> None:
    missing = _codes_raised_in(variations) - GUIDANCE_CODES
    assert not missing, f"no guidance for: {sorted(missing)}"


def test_every_guidance_entry_is_complete() -> None:
    for code in GUIDANCE_CODES:
        entry = guidance_for(code)
        assert isinstance(entry, Guidance)
        assert entry.title.strip()
        assert entry.cause.strip()
        assert entry.fix.strip()
        assert entry.control.strip()


def test_an_unknown_code_still_returns_usable_guidance() -> None:
    entry = guidance_for("something_nobody_wrote")
    assert entry.title.strip()
    assert entry.control.strip()


def test_the_layout_fix_names_a_margin_that_works() -> None:
    entry = guidance_for("no_circles_fit", suggested_margin_mm=6.5)
    assert "6.5" in entry.fix
    assert "6.5" in entry.action_label


def test_the_layout_fix_without_a_suggestion_is_still_useful() -> None:
    entry = guidance_for("no_circles_fit")
    assert entry.fix.strip()
    assert "Outer margin" in entry.control


def test_a_margin_that_would_let_the_circles_fit_is_computed() -> None:
    # A 95 mm badge inside a 60 mm margin leaves 90 mm of usable width on a
    # 210 mm page, so nothing fits until the margin comes down.
    too_tight = CircleSheetConfig(cut_diameter_mm=95.0, margin_mm=60.0, gap_mm=5.0)
    assert compute_circle_sheet_plan(too_tight, CalibrationProfile()).capacity == 0

    suggested = largest_margin_that_fits(too_tight)
    assert suggested is not None
    assert suggested < 60.0

    relaxed = CircleSheetConfig(cut_diameter_mm=95.0, margin_mm=suggested, gap_mm=5.0)
    assert compute_circle_sheet_plan(relaxed, CalibrationProfile()).capacity >= 1


def test_no_margin_helps_when_the_badge_exceeds_the_page() -> None:
    config = CircleSheetConfig(
        cut_diameter_mm=400.0, finished_diameter_mm=400.0, safe_diameter_mm=350.0
    )
    assert largest_margin_that_fits(config) is None


def test_the_suggested_margin_is_a_whole_half_millimetre() -> None:
    config = CircleSheetConfig(cut_diameter_mm=95.0, margin_mm=60.0)
    suggested = largest_margin_that_fits(config)
    assert suggested is not None
    assert (suggested * 2.0) == int(suggested * 2.0)


def test_the_refinement_failures_have_guidance() -> None:
    for code in ("edit_unsupported", "edit_failed"):
        entry = guidance_for(code)
        assert entry.title.strip()
        assert entry.fix.strip()
        assert entry.control.strip()


def test_a_failed_refinement_reassures_that_nothing_was_lost() -> None:
    # A failed edit costs an image charge; the user should not also fear that
    # the picture they had is gone.
    assert "unchanged" in guidance_for("edit_failed").fix.lower()


def test_ink_warnings_have_guidance() -> None:
    assert guidance_for("too_much_ink").control
    assert guidance_for("too_little_ink").control
    assert guidance_for("too_much_ink").action_label
    assert guidance_for("too_little_ink").action_label


def test_the_suggested_margin_accounts_for_calibration() -> None:
    # Measuring the nominal diameter suggested a margin the calibrated layout
    # still could not fit, so taking the offered fix changed nothing.
    stretched = CalibrationProfile(x_scale=1.02, y_scale=1.02)
    config = CircleSheetConfig(cut_diameter_mm=190.0, margin_mm=40.0, gap_mm=5.0)

    assert compute_circle_sheet_plan(config, stretched).capacity == 0

    suggested = largest_margin_that_fits(config, stretched)
    assert suggested is not None

    relaxed = CircleSheetConfig(cut_diameter_mm=190.0, margin_mm=suggested, gap_mm=5.0)
    assert compute_circle_sheet_plan(relaxed, stretched).capacity >= 1


def test_calibration_makes_the_suggestion_no_larger() -> None:
    config = CircleSheetConfig(cut_diameter_mm=190.0, margin_mm=40.0)
    plain = largest_margin_that_fits(config)
    stretched = largest_margin_that_fits(
        config, CalibrationProfile(x_scale=1.02, y_scale=1.02)
    )
    assert plain is not None and stretched is not None
    assert stretched <= plain


def test_a_badge_only_too_large_once_calibrated_is_reported_as_such() -> None:
    config = CircleSheetConfig(
        cut_diameter_mm=208.0, finished_diameter_mm=200.0, safe_diameter_mm=180.0
    )
    assert largest_margin_that_fits(config) is not None
    assert (
        largest_margin_that_fits(config, CalibrationProfile(x_scale=1.05, y_scale=1.05))
        is None
    )
