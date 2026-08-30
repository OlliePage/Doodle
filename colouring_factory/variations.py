from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .generators import GOOGLE_ENDPOINT, GeneratorError
from .providers import get_provider

VARIATION_AXES: dict[str, tuple[str, ...]] = {
    "moment": (
        "the busiest moment of the action",
        "the quiet moment just before it begins",
        "the moment just after it is finished",
        "an unexpected small mishap in the middle of it",
    ),
    "framing": (
        "a wide view showing the whole scene",
        "a close view of the main character's face and hands",
        "a low view looking up at the subject",
        "a side view showing the whole body in profile",
    ),
    "setting": (
        "outdoors on a sunny day",
        "indoors in a cosy room",
        "in a garden with simple large plants",
        "beside water, with simple wide ripples",
    ),
    "mood": (
        "cheerful and energetic",
        "calm and sleepy",
        "proud and pleased",
        "surprised and curious",
    ),
}

_AXIS_ORDER = ("moment", "framing", "setting", "mood")


def axis_briefs(concept: str, count: int) -> tuple[str, ...]:
    """Compose distinct scene briefs by varying four axes independently.

    Each axis advances by a different stride so that four briefs never repeat a
    combination, and a request for fewer alternatives is a prefix of a request
    for more — pressing "another" must not reshuffle pictures already seen.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if count < 1 or count > 4:
        raise ValueError("Between one and four alternatives can be produced.")

    strides = (1, 3, 2, 3)
    offset = sum(ord(character) for character in concept)

    briefs: list[str] = []
    for index in range(count):
        parts = []
        for axis_position, axis_name in enumerate(_AXIS_ORDER):
            values = VARIATION_AXES[axis_name]
            chosen = values[(offset + (index * strides[axis_position])) % len(values)]
            parts.append(chosen)
        moment, framing, setting, mood = parts
        briefs.append(
            f"{concept}, showing {moment}, drawn as {framing}, {setting}, feeling {mood}."
        )
    return tuple(briefs)


_BRIEF_INSTRUCTION = (
    "You plan children's colouring-book pictures. Given one picture idea, write {count} "
    "different scenes that all show that idea. Each scene must differ from the others in the "
    "moment of the story it captures, the camera framing, the setting, and the mood. Never "
    "simply restate the idea. Keep each scene to one sentence a five-year-old could picture, "
    "with no colour words and no text or lettering in the scene.\n\n"
    "Picture idea: {concept}\n\n"
    'Reply with only a JSON array of exactly {count} strings, for example ["...", "..."].'
)


def _extract_json_array(text: str) -> list[str]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    if not stripped.startswith("["):
        bracketed = re.search(r"\[.*\]", stripped, re.DOTALL)
        if not bracketed:
            raise GeneratorError(
                "The text model did not return a list of scenes.", code="brief_format"
            )
        stripped = bracketed.group(0)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise GeneratorError(
            "The text model returned unreadable scenes.", code="brief_format"
        ) from exc
    if not isinstance(parsed, list):
        raise GeneratorError(
            "The text model did not return a list of scenes.", code="brief_format"
        )
    return [str(item).strip() for item in parsed]


def _google_text(model: str, api_key: str, instruction: str) -> str:
    # A plain string rather than the block list used for image generation. The
    # Interactions API types `input` as "Content or array(Content) or
    # array(Step) or string", so both forms are valid; the string is the
    # documented shape for a plain text request.
    request = Request(
        GOOGLE_ENDPOINT,
        data=json.dumps({"model": model, "input": instruction}).encode("utf-8"),
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


def _openai_text(model: str, api_key: str, instruction: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=1)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruction}],
    )
    return str(completion.choices[0].message.content or "")


def written_briefs(
    concept: str,
    count: int,
    *,
    provider_id: str,
    api_key: str,
) -> tuple[str, ...]:
    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")

    spec = get_provider(provider_id)
    if not spec.text_model:
        raise GeneratorError(f"{spec.label} has no text model.", code="no_text_model")
    if not api_key.strip():
        raise GeneratorError(f"{spec.label} is not connected.", code="missing_key")

    instruction = _BRIEF_INSTRUCTION.format(count=count, concept=concept)
    try:
        if spec.id == "google":
            reply = _google_text(spec.text_model, api_key.strip(), instruction)
        else:
            reply = _openai_text(spec.text_model, api_key.strip(), instruction)
    except GeneratorError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise GeneratorError(
            f"Could not reach {spec.label} to plan the scenes.", code="network"
        ) from exc
    except Exception as exc:
        raise GeneratorError(
            f"{spec.label} could not plan the scenes: {exc}", code="brief_failed"
        ) from exc

    briefs = _extract_json_array(reply)
    if len(briefs) != count or any(not brief for brief in briefs):
        raise GeneratorError(
            "The text model returned the wrong number of scenes.", code="brief_format"
        )

    normalised = {re.sub(r"[^a-z0-9]+", " ", brief.lower()).strip() for brief in briefs}
    if len(normalised) != count:
        raise GeneratorError("The text model repeated a scene.", code="brief_format")

    return tuple(briefs)


def build_variation_briefs(
    concept: str,
    count: int,
    *,
    provider_id: str,
    api_key: str,
) -> tuple[str, ...]:
    """Return `count` distinct scene briefs, preferring a written plan.

    A weaker variation beats no picture at all, so every provider failure falls
    back to the deterministic axes rather than propagating.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if count < 1 or count > 4:
        raise ValueError("Between one and four alternatives can be produced.")
    if count == 1:
        return (concept,)

    try:
        return written_briefs(concept, count, provider_id=provider_id, api_key=api_key)
    except (GeneratorError, ValueError):
        return axis_briefs(concept, count)
