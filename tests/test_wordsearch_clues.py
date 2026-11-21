from __future__ import annotations

from pathlib import Path

import pytest

from colouring_factory import generators, wordsearch_clues
from colouring_factory.generators import GeneratorError
from colouring_factory.models import GeneratedArtwork

PNG = (Path(__file__).parent.parent / "assets" / "demo_dinosaur.png").read_bytes()
KWARGS = {"provider_id": "openai", "model": "gpt-image-1", "api_key": "k"}


@pytest.fixture
def requests(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path))
    seen: list[dict] = []

    def fake(**kwargs):
        seen.append(kwargs)
        if "broken" in kwargs["prompts"][0]:
            raise GeneratorError("no", code="boom")
        return [GeneratedArtwork(PNG, kwargs["prompts"][0], "openai", "m")]

    monkeypatch.setattr(generators, "generate_with_provider", fake)
    return seen


def test_prompt_contains_the_word():
    assert "giraffe" in wordsearch_clues.clue_prompt("giraffe")


def test_second_call_uses_the_cache(requests):
    first = wordsearch_clues.clue_picture("cat", **KWARGS)
    second = wordsearch_clues.clue_picture("cat", **KWARGS)
    assert first == second
    assert len(requests) == 1
    assert requests[0]["quality"] == "low"


def test_awkward_word_stays_inside_the_cache(requests, tmp_path):
    wordsearch_clues.clue_picture("../Ice Cream", **KWARGS)
    files = list((tmp_path / "clue_cache").rglob("*.png"))
    assert [f.name for f in files] == ["ice-cream.png"]


def test_one_failure_gives_none_and_the_rest_still_draw(requests):
    result = wordsearch_clues.clue_pictures(["cat", "broken", "dog"], **KWARGS)
    assert result["broken"] is None
    assert result["cat"] and result["dog"]
