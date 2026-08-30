"""Check what Doodle sends OpenAI against what the installed SDK says it takes.

On 2026-08-30 the change-a-picture button sent input_fidelity=0.85 and came
back with "Supported values are: 'high' and 'low'". The unit test passed,
because it asserted the same wrong value the code sent. The OpenAI package
carries the answer in its own type hints, so ask it rather than guessing.
"""

from __future__ import annotations

import inspect
import sys
import types
import typing
from pathlib import Path

import pytest

from colouring_factory import generators

ORIGINAL = (
    Path(__file__).resolve().parents[1] / "assets" / "demo_dinosaur.png"
).read_bytes()


def _allowed_words(annotation: object) -> set[str] | None:
    """Every string a Literal in this annotation permits, or None if free text.

    Returns None when the annotation also accepts a plain string, because then
    no fixed set of words constrains the value.
    """

    words: set[str] = set()
    free = False

    def walk(node: object) -> None:
        nonlocal free
        origin = typing.get_origin(node)
        if origin is typing.Literal:
            for value in typing.get_args(node):
                if isinstance(value, str):
                    words.add(value)
            return
        if node is str:
            free = True
            return
        for argument in typing.get_args(node):
            walk(argument)

    walk(annotation)
    if free or not words:
        return None
    return words


def _capture_edit_request(monkeypatch) -> dict:
    calls: list[dict] = []

    class _Images:
        def edit(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(
                data=[types.SimpleNamespace(b64_json="", url=None)]
            )

    class _Client:
        def __init__(self, **kwargs):
            self.images = _Images()

    fake = types.ModuleType("openai")
    fake.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", fake)

    with pytest.raises(Exception):
        # The fake returns no image bytes, which is fine: the request has
        # already been captured by then.
        generators.refine_with_openai(
            api_key="sk-test",
            image_bytes=ORIGINAL,
            prompt="give the bear a hat",
            model="gpt-image-2",
            size="1024x1536",
            quality="medium",
            closeness=0.85,
        )
    assert calls, "the edit request was never made"
    return calls[0]


def test_every_argument_doodle_sends_exists_on_the_sdk(monkeypatch) -> None:
    openai = pytest.importorskip("openai")
    signature = inspect.signature(openai.resources.images.Images.edit)
    sent = _capture_edit_request(monkeypatch)

    unknown = set(sent) - set(signature.parameters)
    assert not unknown, f"OpenAI's images.edit takes no {sorted(unknown)}"


def test_every_fixed_choice_doodle_sends_is_one_the_sdk_allows(monkeypatch) -> None:
    openai = pytest.importorskip("openai")
    # The SDK stores its annotations as strings, so ask typing to resolve them
    # against the SDK's own module rather than reading the text.
    hints = typing.get_type_hints(openai.resources.images.Images.edit)
    sent = _capture_edit_request(monkeypatch)

    for name, value in sent.items():
        allowed = _allowed_words(hints[name])
        if allowed is None:
            continue
        # Deliberately not restricted to strings. The bug this guards against
        # sent a float to a parameter that takes one of two words.
        assert value in allowed, f"{name}={value!r} is not one of {sorted(allowed)}"


def test_the_helper_itself_recognises_a_fixed_choice() -> None:
    assert _allowed_words(typing.Optional[typing.Literal["high", "low"]]) == {
        "high",
        "low",
    }
    assert _allowed_words(str) is None
    assert _allowed_words(typing.Union[str, typing.Literal["auto"]]) is None
