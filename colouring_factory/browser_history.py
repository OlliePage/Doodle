"""The component that lets the browser's own Back and Forward move the app.

Streamlit redraws nothing when the browser changes only the address's
parameters, so a small invisible custom component (CCv2, `st.components.v2`)
listens for the browser's `popstate` and reports the restored address to
Python as a trigger value. `app.py` registers `LISTENER_JS` each run, and
`step_script` is the one-shot nudge the bar's own arrows give the browser.
"""

from __future__ import annotations

import re

# CCv2 treats a single-line string as a file path rather than inline source,
# so this must stay multi-line. Only v2 APIs here — no
# `Streamlit.setComponentValue`, `window.Streamlit` or postMessage.
LISTENER_JS = """
export default function (component) {
  window.__doodleNavSend = component.setTriggerValue
  if (!window.__doodleNavBound) {
    window.__doodleNavBound = true
    window.addEventListener("popstate", function () {
      if (window.__doodleNavSend) {
        window.__doodleNavSend("moved", window.location.search)
      }
    })
  }
}
"""


def step_script(direction: str, nonce: str) -> str:
    """A `<script>` that moves the browser's history once per `nonce`.

    Mirrors the guard `browser_print.print_trigger_html` uses against its
    print dialogue: Streamlit replays the whole script on every rerun, so
    without a marker that changes, an unrelated rerun would step again.
    The nonce carries the session as well as a count because the tab outlives
    a session: after the app restarts, a bare count starting again at 1 would
    match the last one the page ran, and the first press would be ignored.
    """

    if direction not in ("back", "forward"):
        raise ValueError(f"Unknown navigation direction: {direction!r}")
    if not re.fullmatch(r"[\w.-]+", nonce):
        raise ValueError("A step nonce is required.")

    return (
        "<script>"
        f'if (window.__doodleNavNonce !== "{nonce}") {{ '
        f'window.__doodleNavNonce = "{nonce}"; '
        f"window.history.{direction}(); "
        "}"
        "</script>"
    )
