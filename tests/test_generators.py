from __future__ import annotations

import base64
import sys
import types
from io import BytesIO

from PIL import Image

from colouring_factory.generators import GeneratorError, generate_with_openai


def _png_bytes() -> bytes:
    image = Image.new("RGB", (20, 20), "white")
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_openai_adapter_decodes_base64_and_passes_output_settings(monkeypatch) -> None:
    calls: list[dict] = []
    encoded = base64.b64encode(_png_bytes()).decode("ascii")

    class _Images:
        def generate(self, **kwargs):
            calls.append(kwargs)
            item = types.SimpleNamespace(
                b64_json=encoded, url=None, revised_prompt=None
            )
            return types.SimpleNamespace(data=[item])

    class _Client:
        def __init__(self, **kwargs):
            self.init_kwargs = kwargs
            self.images = _Images()

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    output = generate_with_openai(
        api_key="test-key",
        prompts=["A line drawing of a bear", "A line drawing of a kite"],
        model="gpt-image-2",
        size="1024x1024",
        quality="low",
    )

    assert len(output) == 2
    assert output[0].image_bytes.startswith(b"\x89PNG")
    assert calls[0]["model"] == "gpt-image-2"
    assert calls[0]["size"] == "1024x1024"
    assert calls[0]["quality"] == "low"
    assert calls[0]["background"] == "opaque"

    # Each prompt is sent verbatim. The generator used to append its own
    # "alternative N of M" sentence, which produced near-identical pictures;
    # distinctness is now the caller's job.
    assert calls[0]["prompt"] == "A line drawing of a bear"
    assert calls[1]["prompt"] == "A line drawing of a kite"


def test_openai_adapter_requires_key() -> None:
    try:
        generate_with_openai(api_key="", prompts=["test"])
    except GeneratorError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected missing API key to fail")
