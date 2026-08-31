from __future__ import annotations

from collections.abc import Sequence
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

# Shared by every builder below, so the colouring-book contract cannot drift
# between a fresh drawing, a refinement, a character scene and a caricature.
VISUAL_RULES = (
    "- Pure white background.\n"
    "- Black line work only: no colour, grey, shading, shadows, gradients or hatching.\n"
    "- Every enclosed shape must be left white, so it can be coloured in.\n"
    "- Coherent anatomy and friendly expressions.\n"
    "- No border, words, letters, numbers, logos, signatures or watermark.\n"
    "- Nothing important may be cropped by the image edge."
)

CHARACTER_LIKENESS_RULE = (
    "The attached pictures are the reference for how these characters really "
    "look. Draw each one as a friendly cartoon who is unmistakably recognisable "
    "as that particular character rather than a generic one. Draw hair as one or "
    "two large closed shapes that follow its real shape and length, never as "
    "separate strands. Show markings, worn patches and freckles as outlined "
    "shapes to colour, never as shading."
)

# A face is small on a page and carries all of the recognition, so it gets its
# own allowance while the rest of the sheet stays colourable. Without this, a
# face at the toddler level comes back as a stock cartoon child wearing the
# reference's glasses; with it, the same page keeps its big simple trees.
FACE_DETAIL_EXEMPTION = (
    "Detail exception, which overrides the reader profile for one part of the "
    "picture only: each person's head — the face, the hair and the glasses — may "
    "carry as much fine line work as it takes to be recognisably them, and should "
    "be drawn larger in the frame than realistic proportion would suggest. "
    "Everything else in the picture, including bodies, clothes and the whole "
    "setting, obeys the reader profile exactly: few, large, simple shapes with "
    "wide gaps."
)

# The polite version of this rule was ignored: told to leave the corners empty,
# the model filled them with a garden and added a decorative border. Refusing
# each thing by name is what worked.
BADGE_CORNERS_RULE = (
    "Composition rules for a round badge, which override everything else:\n"
    "- This picture will be cut into a circle. The four corners of the square are "
    "cut away and thrown out, so they must be left completely blank white.\n"
    "- Draw NOTHING in the corners: no background, no scenery, no border, no "
    "frame, no circle, no decorative edge of any kind.\n"
    "- The background behind the subject must be plain empty white. Do not invent "
    "a setting, a room, a garden, foliage or a pattern.\n"
    "- Place the whole head and shoulders inside an imaginary circle that touches "
    "the four edges of the square, centred, filling most of that circle."
)

ORDINALS = (
    "first",
    "second",
    "third",
    "fourth",
    "fifth",
    "sixth",
    "seventh",
    "eighth",
)


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
    {VISUAL_RULES}

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
    {VISUAL_RULES}

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


def build_character_scene_prompt(
    concept: str,
    characters: Sequence[tuple[str, str, str]],
    *,
    age_profile: str = "2-3 years",
    style_name: str = "Toddler bold",
    target: str = "A4 page",
    extra_instructions: str = "",
    variation_brief: str = "",
) -> str:
    """A scene starring saved characters, drawn from their reference pictures.

    `characters` is (name, kind, marks) in the same order the reference pictures
    are attached, because that order is the only thing telling the model which
    face is which.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if not characters:
        raise ValueError("At least one character is required.")

    scene = variation_brief.strip() or concept
    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Toddler bold"])
    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS[DEFAULT_LEVEL])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    introductions = []
    for index, (name, kind, marks) in enumerate(characters):
        ordinal = ORDINALS[index] if index < len(ORDINALS) else f"number {index + 1}"
        article = "person" if kind == "person" else "character"
        line = f"The {ordinal} picture is {name}, a {article}."
        if marks.strip():
            line += f" {marks.strip()}"
        introductions.append(line)

    exemption = (
        f"\n{FACE_DETAIL_EXEMPTION}\n"
        if any(kind == "person" for _, kind, _ in characters)
        else ""
    )

    prompt = f"""
    Create an original black-and-white colouring-book illustration for {level.reader}.

    Scene: {scene}

    Who is in it:
    {chr(10).join(introductions)}

    {CHARACTER_LIKENESS_RULE}
    {exemption}
    Visual rules:
    {VISUAL_RULES}

    Style profile: {style.instruction}
    Reader profile: {level.regions}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    Composition profile: {target_rule}
    """

    if extra_instructions.strip():
        prompt += f"\nAdditional direction: {extra_instructions.strip()}\n"

    return dedent(prompt).strip()


def build_caricature_prompt(
    name: str, kind: str, marks: str, *, age_profile: str = "6-9 years"
) -> str:
    """A head-and-shoulders caricature, composed for a round badge.

    The default level is 6-9 rather than the toddler default because a
    caricature is nothing but a face, so the detail belongs everywhere.
    """

    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS["6-9 years"])
    subject = "person" if kind == "person" else "character"
    marks_line = f" {marks.strip()}" if marks.strip() else ""

    prompt = f"""
    Create an original black-and-white colouring-book caricature.

    Subject: a good-natured caricature of {name}, the {subject} in the attached
    picture, head and shoulders only, facing forward.{marks_line}

    {CHARACTER_LIKENESS_RULE}

    Caricature direction: this is a seaside caricature, so exaggerate boldly and
    comically. Draw the head much larger than the body. Push the two or three
    most distinctive features far beyond life while keeping them unmistakably
    recognisable. Warm and affectionate, never unkind or ugly. A polite,
    accurate, flattering portrait is the wrong answer.

    Visual rules:
    {VISUAL_RULES}

    {BADGE_CORNERS_RULE}

    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    """

    return dedent(prompt).strip()
