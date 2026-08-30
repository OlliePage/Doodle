from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path

from . import __version__

REVISION_ENV_VAR = "DOODLE_BUILD_REV"


@lru_cache(maxsize=1)
def build_revision() -> str:
    """The short git commit for the running code, or an empty string.

    The Docker image is built from a copy with no git history, so the build
    can pass the revision in through the environment instead.
    """

    from_environment = os.getenv(REVISION_ENV_VAR, "").strip()
    if from_environment:
        return from_environment

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip()


def build_label() -> str:
    """Version and revision, for confirming two people run the same code."""

    revision = build_revision()
    return f"v{__version__} · {revision}" if revision else f"v{__version__}"
