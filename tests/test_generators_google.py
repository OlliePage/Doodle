import base64
import json
from io import BytesIO

import pytest

from colouring_factory import generators
from colouring_factory.generators import (
    GeneratorError,
    generate_with_google,
    refine_with_google,
)

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")
PNG_BYTES = b"\x89PNG\r\n\x1a\nfake-png-reference"
JPEG_BYTES = b"\xff\xd8\xfffake-jpeg-reference"


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

    artworks = generate_with_google(
        api_key="AIza-test", prompts=["one", "two", "three"]
    )

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


def _http_error(status: int, body: str):
    from urllib.error import HTTPError

    return HTTPError(
        "https://example", status, "Bad Request", {}, BytesIO(body.encode())
    )


def test_a_400_saying_the_key_is_invalid_is_treated_as_authentication(
    monkeypatch,
) -> None:
    # Google documents 401 for a rejected key but returns 400 with this wording
    # for a malformed one, which fell through to the generic failure message and
    # never offered to replace the key.
    body = '{"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}'

    def fake_urlopen(request, timeout=None):
        raise _http_error(400, body)

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    with pytest.raises(GeneratorError) as caught:
        generate_with_google(api_key="not-a-real-key", prompts=["a bear"])
    assert caught.value.code == "authentication"
    assert "did not accept that API key" in str(caught.value)


def test_a_quota_error_is_treated_as_rate_limiting(monkeypatch) -> None:
    body = '{"error": {"code": 429, "message": "Resource exhausted", "status": "quota_exceeded"}}'

    def fake_urlopen(request, timeout=None):
        raise _http_error(429, body)

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    with pytest.raises(GeneratorError) as caught:
        generate_with_google(api_key="AIza-test", prompts=["a bear"])
    assert caught.value.code == "rate_limit"


def test_each_reference_picture_becomes_its_own_image_block(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _google_reply(_one_image_reply())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    refine_with_google(
        api_key="key",
        prompt="draw them on a beach",
        reference_images=(PNG_BYTES, JPEG_BYTES),
    )

    blocks = captured["body"]["input"]
    assert [block["type"] for block in blocks] == ["text", "image", "image"]
    assert blocks[1]["mime_type"] == "image/png"
    assert blocks[2]["mime_type"] == "image/jpeg"
