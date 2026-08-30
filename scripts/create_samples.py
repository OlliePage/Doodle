from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from colouring_factory.image_processing import normalise_line_art
from colouring_factory.models import CircleSheetConfig, FullPageConfig, ProcessingOptions
from colouring_factory.pdf_export import (
    create_calibration_pdf,
    create_circle_sheet_pdf,
    create_full_page_pdf,
)


SAMPLES = ROOT / "samples"
ASSETS = ROOT / "assets"


def main() -> None:
    SAMPLES.mkdir(exist_ok=True)
    raw = (ASSETS / "demo_dinosaur.png").read_bytes()
    clean = normalise_line_art(
        raw,
        ProcessingOptions(threshold=215, crop_whitespace=True, padding_percent=5, thicken_pixels=0),
    )
    (SAMPLES / "sample_cleaned_dinosaur.png").write_bytes(clean)

    a4 = create_full_page_pdf(
        clean,
        FullPageConfig(caption="Dino gives the little flower a drink."),
    )
    (SAMPLES / "sample_a4_colouring_page.pdf").write_bytes(a4)

    circles, _ = create_circle_sheet_pdf(
        clean,
        CircleSheetConfig(
            finished_diameter_mm=58,
            cut_diameter_mm=58,
            safe_diameter_mm=50,
            margin_mm=10,
            gap_mm=5,
            copies=0,
            show_cut_guide=True,
        ),
    )
    (SAMPLES / "sample_58mm_circle_sheet.pdf").write_bytes(circles)
    (SAMPLES / "printer_calibration.pdf").write_bytes(create_calibration_pdf())


if __name__ == "__main__":
    main()
