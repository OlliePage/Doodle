"""The privacy paragraph on the About tab must state what the code actually does.

A parent reads this text and relies on it. "Everything else stays on this
computer" was written from the steady state alone and quietly omitted that
adding a character sends their photograph to the drawing service once, to
draw the portrait — a comfortable but false claim, fixed on 2026-08-31.

These guard the substance of the disclosure rather than its exact wording, so
the paragraph can still be rewritten without breaking these tests, but not
rewritten back into the same shape of omission without one of them failing.
"""

from __future__ import annotations

import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")


def _about_tab_text() -> str:
    # The privacy paragraph lives on the "About" tab, one of Doodle Studio's
    # tabs, which only renders once the screen falls through every explicit
    # route (home, connect, generate, result, characters, library) to the
    # studio layout beneath them.
    at = AppTest.from_file(APP, default_timeout=60)
    at.session_state["screen"] = "studio"
    at.run()
    assert not at.exception
    return " ".join(block.value for block in at.markdown)


def test_the_privacy_paragraph_discloses_the_photograph_being_sent() -> None:
    text = _about_tab_text()

    # Sentence-split loosely: a rewrite is free to change the words as long
    # as one sentence still names all three facts together — photograph,
    # portrait and sent — which is what a reader needs to understand that
    # the photograph itself once leaves, to become the portrait. Checking
    # "photograph" and "sent" alone is too loose: the old, false paragraph
    # already had both words in one sentence ("...photograph from this
    # computer...it cannot recall anything...already been sent"), about
    # deletion, not about the photograph ever leaving in the first place.
    sentences = re.split(r"(?<=[.!?])\s+", text)
    assert any(
        "photograph" in sentence.lower()
        and "portrait" in sentence.lower()
        and ("sent" in sentence.lower() or "sends" in sentence.lower())
        for sentence in sentences
    ), "no sentence discloses that a photograph is sent to draw the portrait"


def test_the_privacy_paragraph_discloses_the_name_and_marks_being_sent() -> None:
    """FB-10: the paragraph enumerated what leaves as though the list were
    complete, omitting the character's name and the sentence the parent
    wrote describing their face — both sent with every picture alongside
    the photograph (build_caricature_prompt and build_character_scene_prompt
    in colouring_factory/prompts.py both interpolate name and marks)."""

    sentences = re.split(r"(?<=[.!?])\s+", _about_tab_text())
    assert any(
        "name" in sentence.lower()
        and "photograph" in sentence.lower()
        and ("sent" in sentence.lower() or "sends" in sentence.lower())
        for sentence in sentences
    ), "no sentence discloses that the character's name is sent"
    assert any(
        "recognisable" in sentence.lower() or "description" in sentence.lower()
        for sentence in sentences
    ), "no sentence discloses that the marks/description text is sent"


def test_the_privacy_paragraph_does_not_claim_everything_else_stays_put() -> None:
    """Regression guard for the specific false claim this fix removed.

    "Everything else stays on this computer" was true of the steady state
    and false of character creation. The exact phrase is not the only way to
    make that mistake again, but catching its return is cheap and exact.
    """

    text = _about_tab_text().lower()
    assert "everything else stays on this computer" not in text


def test_the_privacy_paragraph_discloses_the_appearance_description_being_sent() -> (
    None
):
    """The same omission FB-10 fixed for `marks` recurred for `appearance`.

    `describe_appearance` drafts a "how they really look" description from
    the photo (colouring_factory/appearance.py), and build_caricature_prompt
    / build_character_scene_prompt both interpolate it alongside `marks` on
    every portrait, scene and badge (colouring_factory/prompts.py). The
    paragraph enumerated only "what makes them recognisable" and stayed
    silent about this second, newer description field.
    """

    sentences = re.split(r"(?<=[.!?])\s+", _about_tab_text())
    assert any(
        "photograph" in sentence.lower()
        and ("sent" in sentence.lower() or "sends" in sentence.lower())
        and "look" in sentence.lower()
        for sentence in sentences
    ), "no sentence discloses that how they look is sent alongside the photograph"


def test_the_privacy_paragraph_explains_a_retried_request_is_ordinary() -> None:
    """FB-14: the OpenAI client is built with `max_retries=2`

    (colouring_factory/generators.py), so a busy or dropped connection can
    resend the whole request, photograph included, up to three times, and
    the parent sees an ordinary success throughout. The paragraph should say
    this plainly rather than let "sent" imply exactly one transmission.
    """

    text = _about_tab_text().lower()
    assert "again" in text and ("dropped connection" in text or "retr" in text), (
        "no mention that a dropped connection can resend the same request"
    )


def test_the_privacy_paragraph_does_not_claim_the_request_is_sent_only_once() -> None:
    """Regression guard: a retry is ordinary and must not be described as a
    single guaranteed transmission."""

    text = _about_tab_text().lower()
    assert "sent once" not in text
    assert "only once" not in text


def test_the_paragraph_discloses_a_dropped_picture_being_sent() -> None:
    """A second door that sends a user's picture to a third party, several
    times per batch. The paragraph is where that is disclosed, and a feature
    that adds a send without adding a sentence makes the whole panel false."""

    text = _about_tab_text()

    sentences = [line for line in text.split(".") if "drag" in line or "drop" in line]
    assert sentences, "nothing in the panel mentions a dropped picture"
    assert "sent" in text
    assert any(
        "four pictures means four sends" in sentence.lower()
        for sentence in text.split(".")
    ), "the paragraph does not say a dropped picture is re-sent per drawing"


def test_the_paragraph_no_longer_claims_the_photograph_is_the_later_likeness() -> None:
    """Commit 2a74542 made every scene draw from the portrait Doodle made, and
    this paragraph went on saying the opposite until 2026-08-31. It is the
    mechanical guard on a claim the code has to keep."""

    text = _about_tab_text()

    assert "likeness always comes from the photograph" not in text
    assert "portrait" in text


def test_the_paragraph_says_how_long_a_dropped_picture_is_held() -> None:
    """It first said "for as long as it is shown in the bar", which is only
    the homepage. The picture survives into the connect, generating and result
    screens, and Draw this idea again re-sends it, so the paragraph named a
    shorter life than the code keeps."""

    text = _about_tab_text()

    assert "for as long as it is shown in the bar" not in text
    assert "New doodle" in text
    assert "Draw this idea again" in text
