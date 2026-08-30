from __future__ import annotations

from pathlib import Path


def assets_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


def list_demo_artwork() -> dict[str, Path]:
    assets = assets_directory()
    return {
        "Dinosaur waters a flower": assets / "demo_dinosaur.png",
        "Bear explores the moon": assets / "demo_bear_astronaut.png",
        "Robot holds balloons": assets / "demo_robot_balloons.png",
    }
