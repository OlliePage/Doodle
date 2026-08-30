"""What Doodle actually puts on the wire, read off a real HTTP request.

Two OpenAI failures reached a user on 2026-08-30 while every test was green,
both about the same argument. The first sent a number where OpenAI takes one of
two words. The second sent that argument to gpt-image-2, which does not accept
it at all, and answered "The model 'gpt-image-2' does not support the
'input_fidelity' parameter".

Mocking the SDK cannot see either mistake, because the mock accepts whatever it
is given. These tests run the genuine OpenAI client against a local server and
read the request body it produced.
"""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from colouring_factory import generators

ORIGINAL = (
    Path(__file__).resolve().parents[1] / "assets" / "demo_dinosaur.png"
).read_bytes()
PIXEL = base64.b64encode(ORIGINAL).decode("ascii")


class _Recorder(BaseHTTPRequestHandler):
    bodies: list[bytes] = []

    def do_POST(self) -> None:  # noqa: N802 - the name http.server requires.
        length = int(self.headers.get("Content-Length", "0"))
        _Recorder.bodies.append(self.rfile.read(length))
        payload = json.dumps({"created": 0, "data": [{"b64_json": PIXEL}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *_args) -> None:
        pass


@pytest.fixture
def wire(monkeypatch):
    """A local stand-in for OpenAI that keeps every request body it is sent."""

    _Recorder.bodies = []
    server = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("OPENAI_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    try:
        yield _Recorder.bodies
    finally:
        server.shutdown()
        server.server_close()


def _refine(model: str) -> None:
    generators.refine_with_openai(
        api_key="sk-test",
        image_bytes=ORIGINAL,
        prompt="colour it in",
        model=model,
        size="1024x1536",
        closeness=0.85,
    )


def test_the_default_model_is_never_asked_for_input_fidelity(wire) -> None:
    _refine("gpt-image-2")

    assert len(wire) == 1
    assert b"input_fidelity" not in wire[0], (
        "gpt-image-2 rejects the whole request when this is present"
    )
    assert b"colour it in" in wire[0]


def test_a_model_that_takes_it_still_gets_it(wire) -> None:
    _refine("gpt-image-1")

    assert b"input_fidelity" in wire[0]
    assert b"high" in wire[0]


def test_the_mini_is_left_out_of_it(wire) -> None:
    _refine("gpt-image-1-mini")

    assert b"input_fidelity" not in wire[0]


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-image-1", True),
        ("gpt-image-1.5", True),
        ("gpt-image-1-2025-04-15", True),
        ("gpt-image-1-mini", False),
        ("gpt-image-2", False),
        ("gpt-image-2-2026-04-21", False),
        ("GPT-Image-2", False),
    ],
)
def test_which_models_take_input_fidelity(model: str, expected: bool) -> None:
    assert generators.openai_supports_input_fidelity(model) is expected
