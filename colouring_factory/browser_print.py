from __future__ import annotations

import base64

# A hidden iframe holding the PDF is the only route a browser gives a page to
# its own print dialogue. The bytes travel inside the page as base64 rather
# than as a link, because Streamlit serves no URL for a PDF it built in memory.
_TEMPLATE = """
<div class="doodle-print-trigger" data-nonce="__NONCE__"></div>
<script>
(function () {
  var nonce = "__NONCE__";
  if (window.__doodlePrintNonce === nonce) { return; }
  window.__doodlePrintNonce = nonce;

  var previous = document.getElementById("doodle-print-frame");
  if (previous) { previous.remove(); }

  var encoded = atob("__PAYLOAD__");
  var bytes = new Uint8Array(encoded.length);
  for (var i = 0; i < encoded.length; i += 1) {
    bytes[i] = encoded.charCodeAt(i);
  }
  var url = URL.createObjectURL(new Blob([bytes], {type: "application/pdf"}));

  var frame = document.createElement("iframe");
  frame.id = "doodle-print-frame";
  frame.setAttribute(
    "style",
    "position:fixed;right:0;bottom:0;width:1px;height:1px;border:0;opacity:0;"
  );
  frame.src = url;
  frame.onload = function () {
    // Chrome needs the embedded viewer a moment after load before it will
    // answer print(); calling straight away prints a blank sheet.
    window.setTimeout(function () {
      try {
        frame.contentWindow.focus();
        frame.contentWindow.print();
        window.__doodlePrintOutcome = "dialogue";
      } catch (error) {
        window.__doodlePrintOutcome = "blocked";
        window.open(url, "_blank");
      }
    }, 300);
  };
  document.body.appendChild(frame);
})();
</script>
"""


def print_trigger_html(pdf_bytes: bytes, *, nonce: str) -> str:
    """A block of HTML that hands the PDF to the browser's print dialogue.

    `nonce` must change every time printing is asked for. Streamlit replays the
    whole script on each rerun, and without a marker that changes, a page that
    reruns for an unrelated reason would raise the print dialogue again.
    """

    if not pdf_bytes:
        raise ValueError("There is no PDF to print.")
    if not nonce:
        raise ValueError("A print nonce is required.")

    payload = base64.b64encode(pdf_bytes).decode("ascii")
    return _TEMPLATE.replace("__PAYLOAD__", payload).replace("__NONCE__", str(nonce))
