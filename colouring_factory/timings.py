"""How long past drawings took, so the waiting screen can say what to expect.

Doodle had never recorded a duration, so a parent watching a blocked screen had
no way to tell a slow drawing from a stuck one. Every finished picture writes
one number here and the next drawing reads them back as a distribution.

Deliberately not an average. A single four-minute timeout among five drawings
drags a mean to 92 seconds against a true typical of 41, and a wrong
expectation is worse than none; a histogram puts that timeout out on the right
where it belongs and leaves the hill alone.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import data_root

BUCKET_SECONDS = 5
BUCKET_COUNT = 18
AXIS_SECONDS = BUCKET_SECONDS * BUCKET_COUNT

# Roughly two years of daily use for one family, and a file small enough that
# reading it while the screen is blocked costs nothing.
MAX_RECORDS = 500

# A clock that jumped, or a duration nobody should learn from.
_LONGEST_PLAUSIBLE_SECONDS = 60 * 30


def timings_path() -> Path:
    """Resolved on every call, never cached, because the data directory is an
    environment variable the tests reassign between cases."""

    return data_root() / "timings.json"


def settings_key(
    *,
    provider: str,
    model: str,
    quality: str,
    size: str,
    with_references: bool,
) -> str:
    """What makes two drawings comparable.

    A picture drawn with photographs of saved characters attached takes
    noticeably longer than one drawn from words alone, and the quality and size
    settings move it again, so times are kept apart by all of them. Anything
    finer would split a household's occasional use into groups too small to
    show a shape.
    """

    references = "refs" if with_references else "words"
    return f"{provider}/{model}/{quality}/{size}/{references}"


def load_timings() -> list[dict[str, Any]]:
    """Every recorded duration, or an empty list for any reason at all.

    Read while the app is already blocked inside a paid network call, so losing
    the history has to be a shrug rather than an exception.
    """

    path = timings_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []

    records: list[dict[str, Any]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            continue
        seconds = entry.get("seconds")
        key = entry.get("key")
        if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
            continue
        if not isinstance(key, str) or not _plausible(float(seconds)):
            continue
        records.append(entry)
    return records


def record_timing(*, seconds: float, settings_key: str) -> None:
    """Add one duration. Never raises: the picture is already drawn and paid
    for by the time this runs, and losing the log must not lose the picture."""

    if not _plausible(seconds):
        return

    records = load_timings()
    records.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "seconds": round(float(seconds), 1),
            "key": settings_key,
        }
    )
    records = records[-MAX_RECORDS:]

    path = timings_path()
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(json.dumps(records, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError:
        return


def recent_durations(
    records: list[dict[str, Any]], limit: int = MAX_RECORDS
) -> list[float]:
    """Every recorded duration, oldest first.

    These were once split by the settings that produced them, on the grounds
    that a batch with photographs attached at high quality is a slower thing
    than a quick sketch. True, and it made the chart useless: a household
    drawing a few times a week never accumulates enough in any one group to
    show a shape, so the screen sat on a sentence apologising for having
    nothing to say. A pooled chart from the first drawing beats a perfect one
    that never arrives. The settings are still written down with each record,
    so splitting them later costs nothing but a decision.
    """

    return [float(entry["seconds"]) for entry in records][-limit:]


def histogram(
    durations: list[float],
    *,
    bucket_seconds: int = BUCKET_SECONDS,
    bucket_count: int = BUCKET_COUNT,
) -> list[int]:
    """How many past drawings fell into each five-second bucket.

    Anything slower than the axis is counted in the last bucket rather than
    dropped, so a timeout still shows up as the far-right bar it deserves to be
    instead of vanishing from the record the parent is being shown.
    """

    counts = [0] * bucket_count
    for seconds in durations:
        index = int(seconds // bucket_seconds)
        counts[min(max(index, 0), bucket_count - 1)] += 1
    return counts


def bar_heights(counts: list[int], *, tallest_px: int, floor_px: int) -> list[int]:
    """Pixel heights for the bars, with a floor so an empty bucket still draws.

    An empty bucket has to remain visible: the marker walks along the whole
    axis, and it would appear to vanish for the first eight buckets of a
    typical wait if nothing were drawn under it.
    """

    tallest = max(counts) if counts else 0
    if tallest <= 0:
        return [floor_px for _ in counts]
    return [max(floor_px, round(count / tallest * tallest_px)) for count in counts]


def _plausible(seconds: float) -> bool:
    return (
        isinstance(seconds, (int, float))
        and not isinstance(seconds, bool)
        and math.isfinite(seconds)
        and 0 < seconds <= _LONGEST_PLAUSIBLE_SECONDS
    )
