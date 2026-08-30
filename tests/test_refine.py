import base64
import json
import sys
import types
from io import BytesIO

import pytest

from colouring_factory import generators
from colouring_factory.generators import (
    GeneratorError,
    refine_with_google,
    refine_with_provider,
    refine_with_recraft,
)

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")
ORIGINAL = b"\x89PNG\r\n\x1a\noriginal-image-bytes"


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_image_reply() -> _FakeResponse:
    payload = {
        "steps": [
            {"type": "model_output", "content": [{"type": "image", "data": PIXEL}]}
        ]
    }
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def _recraft_reply() -> _FakeResponse:
    return _FakeResponse(json.dumps({"data": [{"b64_json": PIXEL}]}).encode("utf-8"))


def test_google_sends_the_instruction_and_the_image_together(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = dict(request.headers)
        return _google_image_reply()

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    art = refine_with_google(
        api_key="AIza-test",
        image_bytes=ORIGINAL,
        prompt="give the bear a hat",
        model="gemini-3.1-flash-image",
        size="3:4",
    )

    blocks = captured["body"]["input"]
    assert blocks[0] == {"type": "text", "text": "give the bear a hat"}
    assert blocks[1]["type"] == "image"
    assert blocks[1]["mime_type"] == "image/png"
    assert base64.b64decode(blocks[1]["data"]) == ORIGINAL
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"
    assert art.image_bytes == b"fake-png-bytes"
    assert art.metadata["instruction"] == "give the bear a hat"


def test_recraft_sends_multipart_with_a_low_strength(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["type"] = request.headers.get("Content-type", "")
        captured["raw"] = request.data
        return _recraft_reply()

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    refine_with_recraft(
        api_key="token",
        image_bytes=ORIGINAL,
        prompt="give the bear a hat",
        model="recraftv4_1",
        closeness=0.85,
    )

    assert captured["url"] == generators.RECRAFT_EDIT_ENDPOINT
    assert captured["type"].startswith("multipart/form-data; boundary=")
    assert ORIGINAL in captured["raw"]
    assert b'name="prompt"' in captured["raw"]

    # strength is difference, so closeness 0.85 must send roughly 0.15, not 0.85.
    body = captured["raw"].decode("latin-1")
    strength = body.split('name="strength"')[1].split("\r\n\r\n")[1].split("\r\n")[0]
    assert float(strength) == pytest.approx(0.15, abs=0.01)


def test_openai_asks_to_stay_faithful_to_the_original(monkeypatch) -> None:
    calls = []

    class _Images:
        def edit(self, **kwargs):
            calls.append(kwargs)
            item = types.SimpleNamespace(b64_json=PIXEL, url=None, revised_prompt=None)
            return types.SimpleNamespace(data=[item])

    class _Client:
        def __init__(self, **kwargs):
            self.images = _Images()

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    generators.refine_with_openai(
        api_key="sk-test",
        image_bytes=ORIGINAL,
        prompt="give the bear a hat",
        model="gpt-image-1",
        size="1024x1536",
        closeness=0.85,
    )

    # OpenAI rejects a number here. This assertion once required the float the
    # rest of Doodle stores, which is how a 400 reached a user pressing Change
    # it on 2026-08-30. The model has to be one that accepts the argument at
    # all; tests/test_openai_wire.py covers which ones do.
    assert calls[0]["input_fidelity"] == "high"
    assert calls[0]["prompt"] == "give the bear a hat"


def test_a_missing_key_is_refused_before_any_request() -> None:
    for provider in ("openai", "google", "recraft"):
        with pytest.raises(GeneratorError) as caught:
            refine_with_provider(
                provider_id=provider,
                api_key="   ",
                image_bytes=ORIGINAL,
                prompt="give it a hat",
                model="m",
                size="3:4",
            )
        assert caught.value.code == "missing_key"


def test_an_unknown_provider_says_so() -> None:
    with pytest.raises(GeneratorError) as caught:
        refine_with_provider(
            provider_id="nonsense",
            api_key="k",
            image_bytes=ORIGINAL,
            prompt="give it a hat",
            model="m",
            size="3:4",
        )
    assert caught.value.code in {"unsupported_provider", "edit_unsupported"}


def test_an_empty_reply_is_explained(monkeypatch) -> None:
    empty = _FakeResponse(json.dumps({"steps": []}).encode("utf-8"))
    monkeypatch.setattr(generators, "urlopen", lambda request, timeout=None: empty)

    with pytest.raises(GeneratorError) as caught:
        refine_with_google(
            api_key="AIza-test",
            image_bytes=ORIGINAL,
            prompt="give it a hat",
            model="gemini-3.1-flash-image",
            size="3:4",
        )
    assert caught.value.code in {"content", "edit_failed"}


def test_an_empty_instruction_is_refused() -> None:
    with pytest.raises(ValueError):
        refine_with_provider(
            provider_id="google",
            api_key="k",
            image_bytes=ORIGINAL,
            prompt="   ",
            model="m",
            size="3:4",
        )


def test_the_multipart_body_round_trips_binary_unchanged() -> None:
    awkward = bytes(range(256))
    body, content_type = generators._multipart_body(
        {"prompt": "hat"}, {"image": ("doodle.png", awkward, "image/png")}
    )
    assert awkward in body
    assert content_type.startswith("multipart/form-data; boundary=")
    boundary = content_type.split("boundary=")[1]
    assert body.endswith(f"--{boundary}--\r\n".encode())


def test_openai_is_only_ever_sent_a_word_it_accepts() -> None:
    for closeness in (0.0, 0.2, 0.49, 0.5, 0.85, 1.0):
        assert generators.openai_input_fidelity(closeness) in {"high", "low"}

    # Closeness runs from 0 to 1, so the halfway point decides which of the two
    # settings a given number means.
    assert generators.openai_input_fidelity(0.85) == "high"
    assert generators.openai_input_fidelity(0.2) == "low"
