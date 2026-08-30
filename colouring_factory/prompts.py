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


@dataclass(frozen=True)
class DetailLevel:
    """How much there is to colour, and how fine the lines that divide it.

    The rungs are far apart on purpose. A six-year-old is bored by the sheet
    drawn for a four-year-old and defeated by the grown-up one, and the whole
    point of the grown-up level is the density that made adult colouring books
    worth an evening.
    """

    label: str
    reader: str
    regions: str
    line_rule: str
    texture_rule: str

    @property
    def is_grown_up(self) -> bool:
        return self.label == "Grown-up"


DETAIL_LEVELS: dict[str, DetailLevel] = {
    "2-3 years": DetailLevel(
        label="2-3 years",
        reader="a toddler",
        regions=(
            "Aim for roughly 6 to 12 large colouring regions. Avoid tiny fingers, fur "
            "texture, patterns, clutter and narrow gaps."
        ),
        line_rule="Very thick, smooth, rounded outlines with wide gaps between them.",
        texture_rule="No pattern, texture or fill of any kind inside a region.",
    ),
    "4-5 years": DetailLevel(
        label="4-5 years",
        reader="a preschool child",
        regions=(
            "Aim for roughly 12 to 28 colouring regions. Some simple clothing, props and "
            "setting details are acceptable, but avoid intricate texture."
        ),
        line_rule="Thick, smooth outlines that a crayon can stay inside.",
        texture_rule="At most a few simple marks, such as spots or stripes on clothing.",
    ),
    "6-9 years": DetailLevel(
        label="6-9 years",
        reader="a school-age child",
        regions=(
            "Aim for roughly 30 to 60 colouring regions. Draw a real setting around the "
            "subject, with foreground and background, and give surfaces their own shapes "
            "to colour."
        ),
        line_rule="Medium, even outlines, thinner for interior detail than for the outline.",
        texture_rule=(
            "Simple repeating pattern is welcome on clothing, leaves, brickwork and "
            "similar surfaces, as long as every shape stays closed and colourable."
        ),
    ),
    "Grown-up": DetailLevel(
        label="Grown-up",
        reader="an adult who colours to unwind",
        regions=(
            "Aim for 150 or more small colouring regions, filling the page corner to "
            "corner with almost no empty white space. Build the scene from layers: the "
            "subject, what surrounds it, a decorative border of repeating motifs, and "
            "patterned fills wherever a plain area would otherwise sit."
        ),
        line_rule=(
            "Fine, even outlines of consistent weight throughout, in the intricate "
            "style of an adult colouring book, mandala or zentangle."
        ),
        texture_rule=(
            "Dense decorative pattern is the point: scales, petals, paisley, dots, "
            "leaves, waves and geometric repeats subdividing every larger area. Every "
            "one of them must be a closed shape a fine pen or pencil can colour, never "
            "a shaded or filled black mass."
        ),
    ),
}

DEFAULT_LEVEL = "2-3 years"

TARGET_RULES = {
    "A4 page": (
        "Use a portrait composition with one obvious main action. Keep the entire subject "
        "within frame and leave useful white space around it."
    ),
    "Round badge": (
        "Use a square composition built for a circular crop. Place the whole subject inside an "
        "imaginary circle that touches the edges of the square, keep every essential feature well "
        "within that circle, and leave the four corners empty. Nothing that matters may sit in a "
        "corner, because the corners are cut away when the badge is made."
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
    variation_brief: str = "",
) -> str:
    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")

    # A brief is one interpretation of the concept; everything else stays
    # identical so alternatives differ in reading, not in drawing conventions.
    scene = variation_brief.strip() or concept

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Toddler bold"])
    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS[DEFAULT_LEVEL])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    prompt = f"""
    Create an original black-and-white colouring-book illustration for {level.reader}.

    Scene: {scene}

    Visual rules:
    - Pure white background.
    - Black line work only: no colour, grey, shading, shadows, gradients or hatching.
    - Every enclosed shape must be left white, so it can be coloured in.
    - Coherent anatomy and friendly expressions.
    - No border, words, letters, numbers, logos, signatures or watermark.
    - Do not imitate or reproduce an existing television, film, book or game character.
    - Nothing important may be cropped by the image edge.

    Style profile: {style.instruction}
    Reader profile: {level.regions}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    Composition profile: {target_rule}
    """

    if extra_instructions.strip():
        prompt += f"\nAdditional direction: {extra_instructions.strip()}\n"

    return dedent(prompt).strip()


def build_refinement_prompt(
    instruction: str,
    *,
    style_name: str = "Toddler bold",
    age_profile: str = "2-3 years",
    target: str = "A4 page",
) -> str:
    """Wrap a change request in the same rules the original drawing obeyed.

    Sent bare, an instruction loses the colouring-book contract and comes back
    shaded or grey, because nothing tells the model the picture is line art
    meant for crayons.
    """

    instruction = instruction.strip()
    if not instruction:
        raise ValueError("Describe the change you would like.")

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Toddler bold"])
    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS[DEFAULT_LEVEL])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    prompt = f"""
    Change this black-and-white colouring-book illustration as described, and
    change nothing else.

    Requested change: {instruction}

    Leave every other part of the scene unchanged: the same characters, poses,
    props, background and composition.

    Visual rules, which the changed picture must still obey:
    - Pure white background.
    - Black line work only: no colour, grey, shading, shadows, gradients or hatching.
    - Every enclosed shape must be left white, so it can be coloured in.
    - Coherent anatomy and friendly expressions.
    - No border, words, letters, numbers, logos, signatures or watermark.
    - Nothing important may be cropped by the image edge.

    Style profile: {style.instruction}
    Reader profile: {level.regions}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    Composition profile: {target_rule}
    """

    return dedent(prompt).strip()


def build_colour_suggestion_prompt() -> str:
    """Ask for a coloured version of the same drawing, as a guide to copy.

    The printable page stays black and white. This is a picture of what the
    finished thing could look like, for a child deciding what colour water,
    grass or a dinosaur's back should be.
    """

    prompt = """
    Colour in this black-and-white line drawing.

    Keep every black outline exactly where it is, at the same weight. Do not
    redraw, move, add or remove anything: the shapes, characters and
    composition must match the original line for line.

    Fill the enclosed areas with flat, bright, friendly colour, the way a
    child's picture book is coloured. Use the colours the real thing would be,
    so that the picture can be copied: sky and water blue, grass and leaves
    green, tree trunks brown, sand and sun yellow. Keep the background white
    wherever the original left it white.

    No shading, gradients, texture, outlines in colour, watermark or text.
    """

    return dedent(prompt).strip()
