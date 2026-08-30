import base64
import json
from io import BytesIO

import pytest

from colouring_factory import generators
from colouring_factory.generators import GeneratorError, generate_with_google

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_reply(payload: dict) -> _FakeResponse:
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def _one_image_reply() -> dict:
    return {
        "model": "gemini-3.1-flash-image",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "image", "mime_type": "image/png", "data": PIXEL}],
            }
        ],
    }


def test_google_returns_decoded_image_bytes(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _google_reply(_one_image_reply())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    artworks = generate_with_google(api_key="AIza-test", prompts=["a bear"], size="3:4")

    assert len(artworks) == 1
    assert artworks[0].image_bytes == b"fake-png-bytes"
    assert artworks[0].provider == "Google Gemini"
    assert captured["url"] == generators.GOOGLE_ENDPOINT
    assert captured["body"]["input"] == [{"type": "text", "text": "a bear"}]
    assert captured["body"]["response_format"]["aspect_ratio"] == "3:4"
    # urllib title-cases header names.
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"


def test_google_makes_one_request_per_prompt(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(json.loads(request.data.decode("utf-8"))["input"][0]["text"])
        return _google_reply(_one_image_reply())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    artworks = generate_with_google(api_key="AIza-test", prompts=["one", "two", "three"])

    assert len(artworks) == 3
    assert len(calls) == 3


def test_google_rejects_a_missing_key() -> None:
    with pytest.raises(GeneratorError) as caught:
        generate_with_google(api_key="  ", prompts=["a bear"])
    assert caught.value.code == "missing_key"


def test_google_explains_a_reply_with_no_image(monkeypatch) -> None:
    reply = {
        "steps": [
            {"type": "model_output", "content": [{"type": "text", "text": "refused"}]}
        ]
    }
    monkeypatch.setattr(
        generators, "urlopen", lambda request, timeout=None: _google_reply(reply)
    )

    with pytest.raises(GeneratorError) as caught:
        generate_with_google(api_key="AIza-test", prompts=["a bear"])
    assert "no image" in str(caught.value).lower()


def test_google_connection_check_uses_the_google_header(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        return _google_reply({"models": []})

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    result = generators.check_provider_connection("google", "AIza-test")

    assert result["valid"] is True
    assert result["provider"] == "Google Gemini"
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"
    assert "Authorization" not in captured["headers"]


def test_openai_connection_check_still_uses_a_bearer_token(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.headers)
        return _google_reply({"data": []})

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    generators.check_provider_connection("openai", "sk-test")

    assert captured["headers"]["Authorization"] == "Bearer sk-test"
