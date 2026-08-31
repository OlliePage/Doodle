"""The waiting screen: the distribution, the clocks and the escalating notes.

The screen moves itself on after every picture, so these freeze the frame the
way tests/test_app_stop_generation.py does — an uncaught error raised from
inside the drawing call stops the script exactly where it is and leaves the
half-drawn frame inspectable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, timings

APP = str(Path(__file__).resolve().parent.parent / "app.py")

KEY = timings.settings_key(
    provider="openai",
    model="gpt-image-2",
    quality="medium",
    size="1024x1536",
    with_references=False,
)


@pytest.fixture(autouse=True)
def _data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for name in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    return tmp_path


def _frozen(monkeypatch, *, idea: str = "a blue dinosaur") -> AppTest:
    """The drawing screen, stopped mid-picture so it can be read."""

    def never_returns(**kwargs):
        raise RuntimeError("stand-in for a drawing that is still going")

    monkeypatch.setattr(generators, "generate_with_provider", never_returns)

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = idea
    at.run()
    return at


def _record(count: int, seconds: float = 44.0) -> None:
    for index in range(count):
        timings.record_timing(seconds=seconds + index, settings_key=KEY)


def test_with_no_history_the_screen_says_so_instead_of_drawing_an_empty_chart(
    monkeypatch,
) -> None:
    """A hill built from nothing would read as an expectation and is not one."""

    at = _frozen(monkeypatch)

    captions = [str(caption.value) for caption in at.caption]
    assert any("has not drawn at these settings before" in text for text in captions)
    assert not any("wait-hist__bars" in str(block.value) for block in at.markdown)


def test_with_history_the_chart_is_drawn_and_counts_the_real_drawings(
    monkeypatch,
) -> None:
    _record(5)
    at = _frozen(monkeypatch)

    charts = [
        str(block.value)
        for block in at.markdown
        if "wait-hist__bars" in str(block.value)
    ]
    assert charts, "the distribution never reached the page"
    chart = charts[0]

    assert chart.count("<i style=") == timings.BUCKET_COUNT
    assert "Your last 5 drawings at these settings" in chart
    assert not any(
        "has not drawn at these settings before" in str(caption.value)
        for caption in at.caption
    )


def test_the_chart_needs_three_drawings_before_it_will_show_a_shape(
    monkeypatch,
) -> None:
    _record(timings.MIN_RECORDS_FOR_CHART - 1)
    at = _frozen(monkeypatch)

    assert not any("wait-hist__bars" in str(block.value) for block in at.markdown)


def test_every_animation_is_named_for_its_picture(monkeypatch) -> None:
    """The markup is identical between pictures of a batch, so a shared
    keyframe name lets the browser carry the old timeline over: picture two
    would open with its chart already coloured in and its "taking a while"
    note already showing. A changed name always restarts an animation."""

    _record(5)
    at = _frozen(monkeypatch)
    chart = next(
        str(block.value)
        for block in at.markdown
        if "wait-hist__bars" in str(block.value)
    )

    for name in ("wait-fill-0", "wait-spark-0", "wait-note-0"):
        assert name in chart, f"{name} is not carrying the picture's index"


def test_the_slow_note_opens_at_the_slowest_drawing_on_record(monkeypatch) -> None:
    """ "Longer than any of those" has to mean the times actually on the chart,
    so the delay is read from them rather than from a fixed number."""

    timings.record_timing(seconds=30.0, settings_key=KEY)
    timings.record_timing(seconds=40.0, settings_key=KEY)
    timings.record_timing(seconds=61.0, settings_key=KEY)

    at = _frozen(monkeypatch)
    chart = next(
        str(block.value)
        for block in at.markdown
        if "wait-hist__bars" in str(block.value)
    )

    assert ".wait-note--slow{animation-delay:61s}" in chart.replace(" ", "").replace(
        "\n", ""
    )
    assert ".wait-note--stuck{animation-delay:240s}" in chart.replace(" ", "").replace(
        "\n", ""
    )


def test_the_four_minute_note_states_what_the_drawing_code_will_really_do(
    monkeypatch,
) -> None:
    """Four minutes and three attempts are not a guess: generators.py builds
    its client with timeout=240.0 and max_retries=2. If either changes, this
    sentence becomes a lie told to a waiting parent."""

    source = (
        Path(__file__).resolve().parent.parent / "colouring_factory" / "generators.py"
    ).read_text()
    assert "timeout=240.0" in source
    assert "max_retries=2" in source

    _record(5)
    at = _frozen(monkeypatch)
    chart = next(
        str(block.value)
        for block in at.markdown
        if "wait-hist__bars" in str(block.value)
    )
    assert "allows four minutes for each attempt" in chart
    assert "up to three attempts in all" in chart


def test_the_typed_idea_is_the_biggest_thing_on_the_screen(monkeypatch) -> None:
    at = _frozen(monkeypatch, idea="a dinosaur on a skateboard")

    blocks = [str(block.value) for block in at.markdown]
    assert any("Now drawing" in text for text in blocks)
    assert any(
        'class="drawing-idea">a dinosaur on a skateboard' in text for text in blocks
    )
    style = next(text for text in blocks if ".drawing-idea{" in text.replace(" ", ""))
    flat = style.replace(" ", "").replace("\n", "")
    assert "font-size:1.5rem" in flat.split(".drawing-idea{")[1][:120]


def test_the_screen_still_keeps_its_count_its_stop_button_and_no_progress_bar(
    monkeypatch,
) -> None:
    """The three things the existing tests pin, re-checked here because this
    change rebuilt the middle of the same screen."""

    _record(5)
    at = _frozen(monkeypatch)

    assert any("Drawing 1 of" in str(block.value) for block in at.markdown)
    assert [button for button in at.button if button.label == "Stop drawing"]
    assert not at.get("progress")


class TestTheTimeItTook:
    def _result(self, seconds: list[float]) -> AppTest:
        artwork = (
            Path(__file__).resolve().parent.parent / "assets" / "demo_dinosaur.png"
        ).read_bytes()
        at = AppTest.from_file(APP, default_timeout=120)
        at.session_state["screen"] = "result"
        at.session_state["current_raw"] = artwork
        at.session_state["quick_processed"] = artwork
        at.session_state["quick_pdf"] = b"%PDF-1.4 test"
        at.session_state["current_title"] = "a blue dinosaur"
        at.session_state["current_metadata"] = {"source": "test"}
        at.session_state["generation_seconds"] = seconds
        at.run()
        return at

    def test_one_picture_reports_its_own_seconds(self) -> None:
        at = self._result([52.4])
        assert any("That took 52 seconds." in str(c.value) for c in at.caption)

    def test_a_batch_reports_the_whole_wait_in_minutes(self) -> None:
        at = self._result([48.0, 44.0, 51.0, 49.0])
        assert any(
            "Those 4 took 3 minutes and 12 seconds altogether." in str(c.value)
            for c in at.caption
        )

    def test_a_batch_under_a_minute_does_not_say_zero_minutes(self) -> None:
        at = self._result([20.0, 21.0])
        assert any(
            "Those 2 took 41 seconds altogether." in str(c.value) for c in at.caption
        )

    def test_nothing_is_claimed_when_nothing_was_timed(self) -> None:
        at = self._result([])
        assert not any(
            "took" in str(c.value) and "second" in str(c.value) for c in at.caption
        )


def test_a_new_batch_does_not_inherit_the_last_one_s_clock(monkeypatch) -> None:
    """Planning a batch clears the running total.

    Without this the second batch of an evening reports its own time plus the
    first one's, and the number the parent is shown grows all night.
    """

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["generation_seconds"] = [99.0, 98.0]

    def never_returns(**kwargs):
        raise RuntimeError("stand-in for a drawing that is still going")

    monkeypatch.setattr(generators, "generate_with_provider", never_returns)
    at.run()

    assert at.session_state["generation_seconds"] == [], (
        "the previous batch's seconds survived into this one"
    )
