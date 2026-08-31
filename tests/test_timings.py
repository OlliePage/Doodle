"""The log of how long past drawings took, and the histogram drawn from it."""

from __future__ import annotations

import json

import pytest

from colouring_factory import timings


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    return tmp_path


KEY = timings.settings_key(
    provider="openai",
    model="gpt-image-2",
    quality="medium",
    size="1024x1536",
    with_references=True,
)


def test_a_fresh_install_has_no_history_and_does_not_mind() -> None:
    assert timings.load_timings() == []
    assert timings.durations_for([], KEY) == []


def test_a_recorded_drawing_comes_back() -> None:
    timings.record_timing(seconds=44.2, settings_key=KEY)

    records = timings.load_timings()
    assert len(records) == 1
    assert records[0]["seconds"] == pytest.approx(44.2)
    assert records[0]["key"] == KEY
    assert timings.durations_for(records, KEY) == [pytest.approx(44.2)]


def test_the_log_never_carries_what_was_drawn() -> None:
    """The privacy tests guard what leaves this machine; this guards what is
    written down at all. A duration is a number, and the idea a child typed has
    no business being stored beside it."""

    timings.record_timing(seconds=44.2, settings_key=KEY)
    written = (timings.timings_path()).read_text()

    for forbidden in ("prompt", "idea", "concept", "name", "character", "photo"):
        assert forbidden not in written.lower(), f"{forbidden} reached the timing log"


def test_times_are_kept_apart_by_the_settings_that_produced_them() -> None:
    """A four-picture batch with two photographs attached at high quality is a
    different animal from one quick sketch, and averaging them together would
    give a wrong expectation rather than no expectation."""

    other = timings.settings_key(
        provider="openai",
        model="gpt-image-2",
        quality="medium",
        size="1024x1536",
        with_references=False,
    )
    assert other != KEY

    timings.record_timing(seconds=44.0, settings_key=KEY)
    timings.record_timing(seconds=12.0, settings_key=other)

    records = timings.load_timings()
    assert timings.durations_for(records, KEY) == [pytest.approx(44.0)]
    assert timings.durations_for(records, other) == [pytest.approx(12.0)]


def test_a_corrupt_or_odd_log_reads_as_empty_rather_than_exploding() -> None:
    """This is read while the screen is already blocked inside a paid network
    call. Losing the history is a shrug; taking the drawing down with it is not.
    """

    path = timings.timings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    for payload in ("", "{", "null", '"a string"', "{}", "[1, 2, 3]"):
        path.write_text(payload)
        assert timings.load_timings() == [], f"{payload!r} should read as empty"

    # A single junk entry loses itself, not the entries around it.
    path.write_text(
        json.dumps(
            [
                {"seconds": 40.0, "key": KEY, "at": "2026-08-31T10:00:00+00:00"},
                {"seconds": "not a number", "key": KEY},
                {"key": KEY},
                "not even an object",
                {"seconds": 50.0, "key": KEY, "at": "2026-08-31T10:01:00+00:00"},
            ]
        )
    )
    assert timings.durations_for(timings.load_timings(), KEY) == [
        pytest.approx(40.0),
        pytest.approx(50.0),
    ]


def test_a_write_that_fails_loses_the_log_and_not_the_drawing(monkeypatch) -> None:
    """The picture has already been drawn and paid for by the time this runs."""

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.write_text", explode)
    timings.record_timing(seconds=44.2, settings_key=KEY)  # must not raise


def test_an_implausible_duration_is_refused() -> None:
    """A negative or absurd number can only come from a clock that jumped, and
    one of those on the chart would mislead every wait afterwards."""

    for bad in (-1.0, 0.0, 60 * 60 * 3.0, float("nan"), float("inf")):
        timings.record_timing(seconds=bad, settings_key=KEY)

    assert timings.load_timings() == []


def test_the_log_does_not_grow_without_end() -> None:
    for index in range(timings.MAX_RECORDS + 25):
        timings.record_timing(seconds=40.0 + index % 7, settings_key=KEY)

    records = timings.load_timings()
    assert len(records) == timings.MAX_RECORDS


class TestTheHistogram:
    def test_each_drawing_lands_in_its_five_second_bucket(self) -> None:
        counts = timings.histogram([2.0, 7.0, 8.0, 44.0])

        assert counts[0] == 1, "2 seconds belongs in the first bucket"
        assert counts[1] == 2, "7 and 8 seconds share the second"
        assert counts[8] == 1, "44 seconds belongs in the ninth"
        assert sum(counts) == 4

    def test_the_chart_is_eighteen_buckets_of_five_seconds(self) -> None:
        assert len(timings.histogram([])) == timings.BUCKET_COUNT
        assert timings.BUCKET_COUNT * timings.BUCKET_SECONDS == timings.AXIS_SECONDS

    def test_a_drawing_slower_than_the_axis_falls_into_the_last_bucket(self) -> None:
        """Rather than off the end of the list, which would lose it silently."""

        counts = timings.histogram([500.0])
        assert counts[-1] == 1
        assert sum(counts) == 1

    def test_bar_heights_are_proportional_with_a_visible_floor(self) -> None:
        """An empty bucket still draws a stub, so the axis reads as an axis
        rather than as a gap, and the marker stays visible walking over it."""

        heights = timings.bar_heights([0, 1, 4], tallest_px=100, floor_px=10)
        assert heights == [10, 25, 100]

    def test_bar_heights_survive_an_empty_history(self) -> None:
        assert timings.bar_heights([0, 0], tallest_px=100, floor_px=10) == [10, 10]
