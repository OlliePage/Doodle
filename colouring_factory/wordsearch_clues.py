from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from colouring_factory import generators
from colouring_factory.generators import GeneratorError
from colouring_factory.image_processing import normalise_line_art
from colouring_factory.models import ProcessingOptions
from colouring_factory.providers import get_provider
from colouring_factory.storage import data_root

# The same cleaning the result screen applies to a first drawing.
_CLEAN = ProcessingOptions(despeckle_size=3)
_MAX_AT_ONCE = 4


def clue_prompt(word: str) -> str:
    return (
        f"A single {word}, centred, as a simple colouring-book drawing for a young "
        "child. Thick, clean black outlines on a plain white background. No "
        "background scenery, no text or letters, no shading, no grey."
    )


def _slug(text: str) -> str:
    # Provider and model ids can hold slashes and colons; a word can hold
    # spaces or punctuation. All of them become one path component.
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "clue"


def _cache_path(word: str, provider_id: str, model: str) -> Path:
    return (
        data_root()
        / "clue_cache"
        / _slug(provider_id)
        / _slug(model)
        / f"{_slug(word)}.png"
    )


def clue_picture(word: str, *, provider_id: str, model: str, api_key: str) -> bytes:
    path = _cache_path(word, provider_id, model)
    if path.is_file():
        return path.read_bytes()

    spec = get_provider(provider_id)
    # Clues are drawn small on the sheet, so the cheapest quality will do.
    # Providers other than OpenAI ignore the argument.
    artworks = generators.generate_with_provider(
        provider_id=provider_id,
        api_key=api_key,
        prompts=[clue_prompt(word)],
        model=model,
        size=spec.square_size,
        quality="low",
    )
    cleaned = normalise_line_art(artworks[0].image_bytes, _CLEAN)

    path.parent.mkdir(parents=True, exist_ok=True)
    # Written then renamed so a concurrent reader never sees half a PNG.
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(cleaned)
    temporary.replace(path)
    return cleaned


def clue_pictures(
    words: list[str], *, provider_id: str, model: str, api_key: str
) -> dict[str, bytes | None]:
    def draw(word: str) -> bytes | None:
        try:
            return clue_picture(
                word, provider_id=provider_id, model=model, api_key=api_key
            )
        except (GeneratorError, ValueError):
            # One missing picture must not stop the sheet being made.
            return None

    with ThreadPoolExecutor(max_workers=_MAX_AT_ONCE) as pool:
        return dict(zip(words, pool.map(draw, words)))
