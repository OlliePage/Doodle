"""Telling the homepage's own controls from the ones inside its popovers.

The interface rule in docs/ui-conventions.md is about page flow: below the
logo the homepage holds one full-width element, the idea box, and the button
that acts on it. What a popover contains when opened is a different question,
and several tests were asserting the two together — the list they pinned
already included "Add a character", which lives inside the cast popover and has
never been on the page.

That conflation only became a problem when the drawing-style picker stopped
being a dropdown and became a row per style, each with its own button. Those
buttons are real, but they are not on the homepage; extending the expected list
to include them would have quietly retired the rule instead of keeping it.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest


def _walk(node, inside_popover: bool, found: list[str]) -> None:
    for child in getattr(node, "children", {}).values():
        kind = getattr(child, "type", type(child).__name__)
        if type(child).__name__ == "Button" and not inside_popover:
            found.append(child.label)
        _walk(child, inside_popover or kind == "popover", found)


def buttons_on_the_page(at: AppTest) -> list[str]:
    """Every button in page flow, ignoring anything a popover holds."""

    found: list[str] = []
    _walk(at.main, False, found)
    return found


def buttons_in_popovers(at: AppTest) -> list[str]:
    """The mirror image: only what a popover holds."""

    page = buttons_on_the_page(at)
    everything = [button.label for button in at.button]
    for label in page:
        if label in everything:
            everything.remove(label)
    return everything
