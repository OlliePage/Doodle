from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class CalibrationProfile:
    """Compensation applied to requested printed dimensions.

    A scale of 1.014 means a 100 mm object is encoded as 101.4 mm in the PDF,
    compensating for a printer that physically outputs 98.6 mm.
    """

    x_scale: float = 1.0
    y_scale: float = 1.0
    x_offset_mm: float = 0.0
    y_offset_mm: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any] | None) -> "CalibrationProfile":
        if not value:
            return cls()
        return cls(
            x_scale=float(value.get("x_scale", 1.0)),
            y_scale=float(value.get("y_scale", 1.0)),
            x_offset_mm=float(value.get("x_offset_mm", 0.0)),
            y_offset_mm=float(value.get("y_offset_mm", 0.0)),
        )


@dataclass(frozen=True)
class ProcessingOptions:
    threshold: int = 215
    auto_invert: bool = True
    crop_whitespace: bool = True
    padding_percent: float = 5.0
    despeckle_size: int = 0
    thicken_pixels: int = 1


@dataclass(frozen=True)
class FullPageConfig:
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    margin_mm: float = 12.0
    caption: str = ""
    caption_font_size_pt: float = 17.0
    caption_area_mm: float = 27.0


@dataclass(frozen=True)
class CircleSheetConfig:
    page_width_mm: float = 210.0
    page_height_mm: float = 297.0
    finished_diameter_mm: float = 58.0
    cut_diameter_mm: float = 58.0
    safe_diameter_mm: float = 50.0
    margin_mm: float = 10.0
    gap_mm: float = 5.0
    copies: int = 0  # 0 means fill the sheet.
    caption: str = ""
    caption_font_size_pt: float = 7.5
    show_cut_guide: bool = True
    show_finished_guide: bool = False
    show_safe_guide: bool = False


@dataclass(frozen=True)
class CustomPageConfig:
    page_width_mm: float = 100.0
    page_height_mm: float = 100.0
    margin_mm: float = 5.0
    caption: str = ""
    caption_font_size_pt: float = 11.0
    caption_area_mm: float = 16.0


@dataclass(frozen=True)
class CirclePlacement:
    centre_x_mm: float
    centre_y_mm: float
    cut_width_mm: float
    cut_height_mm: float


@dataclass(frozen=True)
class CircleSheetPlan:
    columns: int
    rows: int
    capacity: int
    placements: tuple[CirclePlacement, ...] = field(default_factory=tuple)
    effective_cut_width_mm: float = 0.0
    effective_cut_height_mm: float = 0.0


@dataclass(frozen=True)
class GeneratedArtwork:
    image_bytes: bytes
    prompt: str
    provider: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)
