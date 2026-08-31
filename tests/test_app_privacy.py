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


def test_the_privacy_paragraph_does_not_claim_everything_else_stays_put() -> None:
    """Regression guard for the specific false claim this fix removed.

    "Everything else stays on this computer" was true of the steady state
    and false of character creation. The exact phrase is not the only way to
    make that mistake again, but catching its return is cheap and exact.
    """

    text = _about_tab_text().lower()
    assert "everything else stays on this computer" not in text
