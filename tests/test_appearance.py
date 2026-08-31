from __future__ import annotations

import json
import sys
import types
from io import BytesIO

import pytest

from colouring_factory import appearance
from colouring_factory.generators import GeneratorError

PHOTO = b"\x89PNG\r\n\x1a\n" + b"a real photograph would go here"


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_reply(text: str) -> _FakeResponse:
    payload = {
        "steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]
    }
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def test_an_empty_photo_is_refused() -> None:
    with pytest.raises(ValueError):
        appearance.describe_appearance(b"", provider_id="openai", api_key="sk-test")


def test_a_provider_with_no_text_model_is_refused() -> None:
    with pytest.raises(GeneratorError) as excinfo:
        appearance.describe_appearance(PHOTO, provider_id="recraft", api_key="token")
    assert excinfo.value.code == "no_text_model"


def test_a_missing_key_is_refused() -> None:
    with pytest.raises(GeneratorError) as excinfo:
        appearance.describe_appearance(PHOTO, provider_id="openai", api_key="")
    assert excinfo.value.code == "missing_key"


def test_google_reads_the_description_out_of_the_image_call(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _google_reply("Brown eyes, curly dark hair, light-brown skin.")

    monkeypatch.setattr(appearance, "urlopen", fake_urlopen)

    description = appearance.describe_appearance(
        PHOTO, provider_id="google", api_key="AIza-test"
    )

    assert description == "Brown eyes, curly dark hair, light-brown skin."
    # The photo actually has to ride along as an image block, not just get
    # described from the text prompt alone.
    blocks = captured["body"]["input"]
    assert any(block.get("type") == "image" for block in blocks)
    image_block = next(block for block in blocks if block.get("type") == "image")
    assert image_block["data"]


def test_openai_reads_the_description_out_of_the_chat_reply(monkeypatch) -> None:
    captured = {}

    class _Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            message = types.SimpleNamespace(
                content="Blue eyes, straight ginger hair, freckled fair skin."
            )
            choice = types.SimpleNamespace(message=message)
            return types.SimpleNamespace(choices=[choice])

    class _Chat:
        def __init__(self):
            self.completions = _Completions()

    class _Client:
        def __init__(self, **kwargs):
            self.chat = _Chat()

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    description = appearance.describe_appearance(
        PHOTO, provider_id="openai", api_key="sk-test"
    )

    assert description == "Blue eyes, straight ginger hair, freckled fair skin."
    # An image content part must actually be attached, not just a caption.
    content = captured["messages"][0]["content"]
    assert any(part.get("type") == "image_url" for part in content)


def test_a_network_failure_is_reported_plainly(monkeypatch) -> None:
    def explode(request, timeout=None):
        raise TimeoutError("no network")

    monkeypatch.setattr(appearance, "urlopen", explode)

    with pytest.raises(GeneratorError) as excinfo:
        appearance.describe_appearance(PHOTO, provider_id="google", api_key="AIza-test")
    assert excinfo.value.code == "network"


def test_an_empty_reply_is_treated_as_a_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        appearance, "urlopen", lambda request, timeout=None: _google_reply("   ")
    )

    with pytest.raises(GeneratorError) as excinfo:
        appearance.describe_appearance(PHOTO, provider_id="google", api_key="AIza-test")
    assert excinfo.value.code == "appearance_failed"
