from __future__ import annotations

from dataclasses import dataclass
from textwrap import dedent


@dataclass(frozen=True)
class StylePreset:
    label: str
    instruction: str


STYLE_PRESETS: dict[str, StylePreset] = {
    "Toddler bold": StylePreset(
        label="Toddler bold",
        instruction=(
            "Use very thick, smooth, rounded black outlines and only a few large, "
            "clearly enclosed colouring regions. Keep the action immediately legible."
        ),
    ),
    "Preschool detailed": StylePreset(
        label="Preschool detailed",
        instruction=(
            "Use strong rounded outlines with a moderate amount of detail, while keeping "
            "every colouring region comfortably large for a preschool child."
        ),
    ),
    "Badge portrait": StylePreset(
        label="Badge portrait",
        instruction=(
            "Show one central subject, preferably head and upper body, composed inside an "
            "imaginary circle with generous clear space around every edge."
        ),
    ),
    "Simple objects": StylePreset(
        label="Simple objects",
        instruction=(
            "Use one to three familiar objects, oversized and separated, with simple closed "
            "shapes and almost no background detail."
        ),
    ),
}

AGE_RULES = {
    "2-3 years": (
        "Aim for roughly 6 to 12 large colouring regions. Avoid tiny fingers, fur texture, "
        "patterns, clutter and narrow gaps."
    ),
    "4-5 years": (
        "Aim for roughly 12 to 28 colouring regions. Some simple clothing, props and setting "
        "details are acceptable, but avoid intricate texture."
    ),
}

TARGET_RULES = {
    "A4 page": (
        "Use a portrait composition with one obvious main action. Keep the entire subject "
        "within frame and leave useful white space around it."
    ),
    "Round badge": (
        "Use a square composition. Keep all essential features near the centre so the artwork "
        "can be placed safely inside a circular crop. Do not place details in the corners."
    ),
    "Flexible": (
        "Use a balanced, central composition that can tolerate either portrait or square cropping."
    ),
}


def build_colouring_prompt(
    concept: str,
    age_profile: str = "2-3 years",
    style_name: str = "Toddler bold",
    target: str = "A4 page",
    extra_instructions: str = "",
) -> str:
    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Toddler bold"])
    age_rule = AGE_RULES.get(age_profile, AGE_RULES["2-3 years"])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    prompt = f"""
    Create an original black-and-white colouring-book illustration for a young child.

    Scene: {concept}

    Visual rules:
    - Pure white background.
    - Black line work only: no colour, grey, shading, shadows, gradients, hatching or texture.
    - Smooth rounded outlines, friendly expressions and coherent anatomy.
    - Large, closed areas that are pleasant to colour with crayons.
    - No border, words, letters, numbers, logos, signatures or watermark.
    - Do not imitate or reproduce an existing television, film, book or game character.
    - Nothing important may be cropped by the image edge.

    Style profile: {style.instruction}
    Child profile: {age_rule}
    Composition profile: {target_rule}
    """

    if extra_instructions.strip():
        prompt += f"\nAdditional direction: {extra_instructions.strip()}\n"

    return dedent(prompt).strip()
