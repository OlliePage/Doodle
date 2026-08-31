from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .generators import GOOGLE_ENDPOINT, GeneratorError, mime_for
from .providers import get_provider

# What actually gets asked for, once, when a character is added: a plain,
# respectful description a person would give a friend drawing them, not a
# system logging attributes. Everything downstream — the line art and the
# colour suggestion alike — reads this one sentence rather than the photo.
_APPEARANCE_INSTRUCTION = (
    "Look at the attached photograph and describe, in one or two plain, "
    "factual sentences, what this person or thing actually looks like: "
    "hair colour and texture, eye colour, skin tone, and any other feature "
    "that would matter to someone drawing and colouring a picture of them "
    "— glasses, freckles, a favourite jumper, or a toy's worn patches and "
    "ribbon colour. Write the way a person would describe a friend to "
    "someone drawing them, not the way a system logs attributes. Reply "
    "with only the description, nothing else."
)


def _openai_vision_text(model: str, api_key: str, photo: bytes) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=1)
    encoded = base64.b64encode(photo).decode("ascii")
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _APPEARANCE_INSTRUCTION},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_for(photo)};base64,{encoded}"
                        },
                    },
                ],
            }
        ],
    )
    return str(completion.choices[0].message.content or "")


def _google_vision_text(model: str, api_key: str, photo: bytes) -> str:
    # The same endpoint and input shape refine_with_google already sends: a
    # text block followed by an image block, rather than the plain string
    # _google_text uses when there is no picture to attach.
    body = {
        "model": model,
        "input": [
            {"type": "text", "text": _APPEARANCE_INSTRUCTION},
            {
                "type": "image",
                "mime_type": mime_for(photo),
                "data": base64.b64encode(photo).decode("ascii"),
            },
        ],
    }
    request = Request(
        GOOGLE_ENDPOINT,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for step in payload.get("steps") or ():
        for block in step.get("content") or ():
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", ""))
    return ""


def describe_appearance(photo: bytes, *, provider_id: str, api_key: str) -> str:
    """Ask the connected provider what this person or thing actually looks like.

    One call, made when a character is added, so the colouring a photograph
    could have carried survives into the black-and-white portrait's prompt
    and, later, into the finished colour suggestion. Recraft has no text
    model at all, so it is refused here the same way written_briefs refuses
    it for scene planning, rather than being asked and failing lower down.
    """

    if not photo:
        raise ValueError("A photograph is required.")

    spec = get_provider(provider_id)
    if not spec.text_model:
        raise GeneratorError(f"{spec.label} has no text model.", code="no_text_model")
    if not api_key.strip():
        raise GeneratorError(f"{spec.label} is not connected.", code="missing_key")

    try:
        if spec.id == "google":
            reply = _google_vision_text(spec.text_model, api_key.strip(), photo)
        else:
            reply = _openai_vision_text(spec.text_model, api_key.strip(), photo)
    except GeneratorError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise GeneratorError(
            f"Could not reach {spec.label} to describe the photograph.",
            code="network",
        ) from exc
    except Exception as exc:
        raise GeneratorError(
            f"{spec.label} could not describe the photograph: {exc}",
            code="appearance_failed",
        ) from exc

    description = reply.strip()
    if not description:
        raise GeneratorError(
            f"{spec.label} returned no description.", code="appearance_failed"
        )
    return description
