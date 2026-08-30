import base64
import json
from io import BytesIO

from colouring_factory import generators
from colouring_factory.generators import generate_with_provider

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def test_each_prompt_is_sent_exactly_as_given(monkeypatch) -> None:
    sent = []

    def fake_urlopen(request, timeout=None):
        sent.append(json.loads(request.data.decode("utf-8"))["input"][0]["text"])
        payload = {
            "steps": [
                {"type": "model_output", "content": [{"type": "image", "data": PIXEL}]}
            ]
        }
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    artworks = generate_with_provider(
        provider_id="google",
        api_key="AIza-test",
        prompts=["first scene", "second scene"],
        model="gemini-3.1-flash-image",
        size="3:4",
    )

    assert sent == ["first scene", "second scene"]
    assert [art.prompt for art in artworks] == ["first scene", "second scene"]


def test_the_old_variant_helper_is_gone() -> None:
    # The generator no longer invents the difference between variants; the
    # caller supplies one prompt per picture.
    assert not hasattr(generators, "_variant_prompt")
