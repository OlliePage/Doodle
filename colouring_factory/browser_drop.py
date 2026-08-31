from __future__ import annotations

import json
from collections.abc import Sequence

# What a drop is allowed to be. The same tuple feeds the hidden uploader's
# type= list and the check this script makes before injecting, so the browser
# and the widget can never disagree about what counts as a picture.
#
# "heif" is here alongside "heic" because an iPhone hands over both: a file
# named live.heif was refused outright by Streamlit's own filter when only
# "heic" was declared, tested on 2026-08-31.
DROP_EXTENSIONS: tuple[str, ...] = ("png", "jpg", "jpeg", "webp", "heic", "heif")

# Streamlit's own ceiling, from .streamlit/config.toml's maxUploadSize = 200.
# Kept in Python rather than read from the config because this constant has to
# be baked into a script that never varies; see the note on the template below.
DROP_MAX_BYTES: int = 200 * 1024 * 1024

# The payload must be byte-identical on every rerun. Streamlit reuses the DOM
# node for an unchanged st.html block and never re-inserts the script, so one
# overlay and one set of window listeners exist for the life of the page.
# Vary the payload — a nonce, the screen name, anything read from session
# state — and the block remounts on every rerun. Measured on 2026-08-31 in
# headless Chrome: four overlays, twelve window listeners, and a single user
# drop handled four times over. browser_print.py's nonce is deliberately not
# copied here, because printing wants to re-fire and this does not.
#
# The window.__doodleDrop guard is the second line of defence rather than the
# first: it holds the count to one even when something does change the payload.
_TEMPLATE = """
<div class="doodle-drop-anchor"></div>
<style>
  #doodle-drop-overlay {
    position: fixed;
    inset: 0;
    z-index: 2147483000;
    display: none;
    align-items: center;
    justify-content: center;
    background: rgba(255, 255, 255, 0.92);
    -webkit-backdrop-filter: blur(2px);
    backdrop-filter: blur(2px);
  }
  #doodle-drop-overlay .doodle-drop-panel {
    /* pointer-events off, or the panel itself becomes a dragleave boundary
       and the overlay flickers as the pointer crosses onto it. */
    pointer-events: none;
    box-sizing: border-box;
    width: min(680px, 78vw);
    padding: 72px 48px;
    border: 2px dashed #c9cdd3;
    border-radius: 20px;
    background: #f7f7f8;
    color: #171717;
    text-align: center;
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    font-size: 19px;
    font-weight: 500;
    line-height: 1.45;
  }
  #doodle-drop-overlay.doodle-drop-refused .doodle-drop-panel {
    border-color: #b45309;
    background: #fffbeb;
    color: #7c2d12;
  }
</style>
<script>
(function () {
  if (window.__doodleDrop) { return; }
  window.__doodleDrop = true;

  var ACCEPTED = __ACCEPTED__;
  var MAX_BYTES = __MAX_BYTES__;
  var INVITE = "Drop a picture to draw with";

  var overlay = document.createElement("div");
  overlay.id = "doodle-drop-overlay";
  var panel = document.createElement("div");
  panel.className = "doodle-drop-panel";
  panel.textContent = INVITE;
  overlay.appendChild(panel);
  // Appended to the body rather than left inside this block: st.html clears
  // its own div when Streamlit unmounts it, and an overlay written into the
  // markup would go with it. Living outside Streamlit's managed tree is what
  // makes it survive every rerun.
  document.body.appendChild(overlay);

  var depth = 0;
  var settling = null;

  function show(message, refused) {
    panel.textContent = message;
    if (refused) {
      overlay.classList.add("doodle-drop-refused");
    } else {
      overlay.classList.remove("doodle-drop-refused");
    }
    overlay.style.display = "flex";
  }

  function hide() {
    overlay.style.display = "none";
    overlay.classList.remove("doodle-drop-refused");
    panel.textContent = INVITE;
  }

  function linger(message) {
    // A refusal has to outlive the drop that caused it. The pointer has
    // already left by the time we know the file is wrong, so no later drag
    // event will redraw this panel and nothing else on the page will say so.
    show(message, true);
    window.clearTimeout(settling);
    settling = window.setTimeout(hide, 2800);
  }

  function carriesFile(event) {
    var types = event.dataTransfer && event.dataTransfer.types;
    if (!types) { return false; }
    for (var i = 0; i < types.length; i += 1) {
      if (types[i] === "Files") { return true; }
    }
    return false;
  }

  function extensionOf(name) {
    var text = String(name || "");
    var dot = text.lastIndexOf(".");
    return dot < 0 ? "" : text.slice(dot + 1).toLowerCase();
  }

  window.addEventListener("dragenter", function (event) {
    if (!carriesFile(event)) { return; }
    event.preventDefault();
    depth += 1;
    window.clearTimeout(settling);
    show(INVITE, false);
  }, true);

  window.addEventListener("dragover", function (event) {
    if (!carriesFile(event)) { return; }
    // Without this the browser takes the drop itself and navigates away from
    // Doodle to display the file, losing whatever was on screen.
    event.preventDefault();
  }, true);

  window.addEventListener("dragleave", function (event) {
    if (!carriesFile(event)) { return; }
    depth -= 1;
    // dragleave fires on every child boundary the pointer crosses, so without
    // counting enters against leaves the panel flickers its way across the
    // page as the pointer moves over each element beneath it.
    if (depth <= 0) {
      depth = 0;
      hide();
    }
  }, true);

  window.addEventListener("drop", function (event) {
    if (!carriesFile(event)) { return; }
    event.preventDefault();
    depth = 0;

    var file = event.dataTransfer.files && event.dataTransfer.files[0];
    if (!file) { hide(); return; }

    // Both checks below exist because Streamlit's own refusal is invisible
    // here. It writes "Error: ... files are not allowed." as text inside the
    // uploader's own block, which is the block being hidden, and fires no
    // rerun at all — so anything this handler does not catch itself reaches
    // the parent as complete silence. Verified in headless Chrome 2026-08-31.
    if (ACCEPTED.indexOf(extensionOf(file.name)) < 0) {
      linger("Doodle can draw from a photo, not from that kind of file");
      return;
    }
    if (file.size > MAX_BYTES) {
      linger("That picture is too big for Doodle to take");
      return;
    }

    // Resolved here and never at setup time: this script runs before the
    // elements declared below it in app.py have rendered, so a reference
    // taken when the block mounts is null for the life of the page.
    var input = document.querySelector(
      '.st-key-doodle-drop-well input[data-testid="stFileUploaderDropzoneInput"]'
    );
    if (!input) {
      linger("There is nowhere for a picture to go on this screen");
      return;
    }

    // React handles input[type=file] through the native change event rather
    // than its own value tracker, so assigning .files and dispatching a
    // bubbling change is enough; no private _valueTracker hack is needed.
    var carrier = new DataTransfer();
    carrier.items.add(file);
    input.files = carrier.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
    hide();
  }, true);
})();
</script>
"""


def drop_overlay_html(
    *,
    accepted: Sequence[str] = DROP_EXTENSIONS,
    max_bytes: int = DROP_MAX_BYTES,
) -> str:
    """The whole-page drop target: one block of HTML, CSS and JavaScript.

    Both arguments are Doodle's own constants and are validated as such. This
    template is handed to ``st.html(..., unsafe_allow_javascript=True)``, so a
    filename, a prompt or a character's name interpolated into it would be
    script injection rather than a string. The alphanumeric check below is what
    makes "nothing user-supplied reaches this template" a rule the code keeps
    rather than a promise the caller has to remember.

    Calling this twice with the same arguments must return the same bytes; see
    the note on the template.
    """

    cleaned = [str(item).lower().lstrip(".") for item in accepted]
    if not cleaned:
        raise ValueError("At least one accepted extension is required.")
    if not all(item.isalnum() for item in cleaned):
        raise ValueError("An accepted extension must be alphanumeric.")
    if int(max_bytes) <= 0:
        raise ValueError("A positive size ceiling is required.")

    return _TEMPLATE.replace("__ACCEPTED__", json.dumps(cleaned)).replace(
        "__MAX_BYTES__", str(int(max_bytes))
    )
