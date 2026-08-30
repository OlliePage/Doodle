from __future__ import annotations

import base64
from urllib.request import urlopen

from .models import GeneratedArtwork


class GeneratorError(RuntimeError):
    pass


def generate_with_openai(
    *,
    api_key: str,
    prompt: str,
    variants: int = 1,
    model: str = "gpt-image-2",
    size: str = "1024x1536",
    quality: str = "low",
) -> list[GeneratedArtwork]:
    """Generate one or more images using the OpenAI Images API.

    Requests are deliberately made one at a time. This is compatible with
    models that do not expose multi-image generation through a single call and
    makes partial failures easier to explain in the UI.
    """

    if not api_key.strip():
        raise GeneratorError("Enter an OpenAI API key before generating artwork.")
    if variants < 1 or variants > 4:
        raise GeneratorError("Variants must be between 1 and 4.")

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - exercised only in an incomplete install.
        raise GeneratorError(
            "The OpenAI Python package is not installed. Run pip install -r requirements.txt."
        ) from exc

    try:
        client = OpenAI(api_key=api_key.strip(), timeout=240.0, max_retries=2)
    except Exception as exc:
        raise GeneratorError(f"Could not initialise the OpenAI client: {exc}") from exc

    images: list[GeneratedArtwork] = []
    for index in range(variants):
        variant_prompt = prompt
        if variants > 1:
            variant_prompt += (
                f"\nProduce visual alternative {index + 1} of {variants}; vary the pose or prop "
                "while preserving every style and composition rule."
            )

        try:
            result = client.images.generate(
                model=model,
                prompt=variant_prompt,
                size=size,
                quality=quality,
                background="opaque",
            )
            if not result.data:
                raise GeneratorError("The image service returned no image data.")
            item = result.data[0]
            encoded = getattr(item, "b64_json", None)
            url = getattr(item, "url", None)
            if encoded:
                image_bytes = base64.b64decode(encoded)
            elif url:
                with urlopen(url, timeout=120) as response:  # nosec B310 - URL is provider supplied.
                    image_bytes = response.read()
            else:
                raise GeneratorError("The image response contained neither base64 data nor a URL.")
        except GeneratorError:
            raise
        except Exception as exc:
            raise GeneratorError(f"Image generation failed: {exc}") from exc

        metadata = {
            "variant": index + 1,
            "size": size,
            "quality": quality,
        }
        revised_prompt = getattr(item, "revised_prompt", None)
        if revised_prompt:
            metadata["revised_prompt"] = revised_prompt

        images.append(
            GeneratedArtwork(
                image_bytes=image_bytes,
                prompt=variant_prompt,
                provider="OpenAI",
                model=model,
                metadata=metadata,
            )
        )

    return images
