from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from textwrap import dedent, indent


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
    "as that particular character rather than a generic one. Follow each one's "
    "real face shape and their real hair length, parting and wave. Draw the "
    "hair as its outline plus a few large closed wave shapes inside it, never "
    "as many fine separate strands or hairline texture. Show markings, worn "
    "patches and freckles as outlined shapes to colour, never as shading."
)

# Flattening hair into "one or two large closed shapes" was written to protect
# the despeckle pass from strands a pixel wide, and it cost more than it saved:
# hair length and parting are most of what makes a child recognisable at a
# glance, and erasing them was part of why every drawn child came back the
# same. Measured on 2026-08-31 across six drawings of the same two girls, the
# wording above survives the print-clean pass with no ink lost at all (every
# variant gained ink, 121% to 140% of the original, because cleaning turns
# grey lines solid black) and lands at 12.5% to 13.6% coverage against the 35%
# mark where Doodle warns a page is too dark.

# The library shows a drawing of each character, and that drawing is the
# promise. Scenes used to be drawn from the photograph instead, which made them
# a second, independent reading of the same face — close, but not the same
# child, and worse than the one advertised. Sending the drawing itself is what
# keeps the promise. Four versions of one scene on 2026-08-31 settled it: from
# the photograph alone the girls came back generic; from the drawing alone a
# starfish hairclip that exists nowhere but the library portrait appeared in
# the scene, and both faces matched what the library showed. Ink coverage went
# from 10.24% to 9.42%, so the match costs nothing in colourability.
#
# Sending the photograph as well was tried and dropped. It was no better than
# the drawing alone and in places worse, giving one girl a ponytail her
# portrait does not have, because two references of one face invite an average
# of the two. It also cost a reference slot per character, halving how many
# could appear in one picture.
PORTRAIT_MATCH_RULE = (
    "Each attached picture is the line drawing Doodle has already made of that "
    "character and shows their family. It is the authority on how they are "
    "drawn. Copy the face from it \u2014 the shape of the eyes, the nose, the "
    "mouth, the eyebrows, the hairline and the way the hair falls \u2014 so "
    "that the character in your picture and the character in that drawing are "
    "plainly the same one drawn twice, not two who look similar. Keep every "
    "particular thing it shows, down to a hair clip or a pattern on a top."
)

GENERIC_FACE_REFUSAL = (
    "A generic cartoon child with large round eyes and a button nose is the "
    "wrong answer and will be rejected."
)

TOLD_APART_RULE = (
    "If the people in the picture cannot be told apart from one another, you "
    "have not followed this instruction."
)

# A face needs room on the page before any wording can put a likeness into it.
# Asked for a walk in a forest, the model drew three full-length figures in a
# landscape and gave each head about a ninth of the picture's height, which at
# this size is a hundred-odd pixels: too few for the features that make one
# child different from another. Drawing them close and cropped at the waist is
# what fixed it, and it leaves the scene behind them intact.
CAST_FOREGROUND_RULE = (
    "Composition override for the named characters, which takes precedence "
    "over the composition profile: place them in the near foreground, standing "
    "close to the viewer, cropped at the waist or thigh rather than drawn head "
    "to toe. Each named character's head must be at least one fifth of the "
    "picture's height. The setting goes behind them and may be as simple as it "
    "likes. A wide shot of small full-length figures in a large landscape is "
    "the wrong answer."
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

# "Person" and "toy" each need their own instruction because they fail in
# opposite directions: a face gets smoothed into a generic child (the
# exemption above), while a toy gets tidied into a fresh one from a shop
# shelf, losing the exact wear that makes it that toy. "Character" is a third
# thing again — an existing design, not a real object — so it needs telling
# to keep that design rather than reinterpreting the idea of it.
_KIND_ARTICLES = {"person": "person", "toy": "toy", "character": "character"}

TOY_LIKENESS_RULE = (
    "This one is a toy, not a living thing. Keep it looking like this exact "
    "toy, not a fresh one from a shop shelf: keep its worn patches, its "
    "visible stitching and any odd or mismatched button, ear or eye exactly "
    "as it really is, rather than tidying them away."
)

NAMED_CHARACTER_RULE = (
    "This one is an existing character, not a new invention. Keep their own "
    "particular design — proportions, line weight and styling — rather than "
    "a generic reinterpretation of the idea of them."
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

# A photograph is where a person's actual colouring lives, and it is gone by
# the time a black-and-white drawing exists: a model asked to colour a line
# drawing of a child with no information reaches for a default, which is how
# a mixed-race child with brown hair and brown eyes came back blonde and
# pink-skinned. The polite version of the other rules in this file
# ("the colours the real thing would be") already existed and was not
# enough, so this one is as blunt as BADGE_CORNERS_RULE and the caricature
# direction above had to become before either was obeyed.
CHARACTER_COLOUR_RULE = (
    "Colouring rules for the real people and toys in this picture, which "
    "override every general colour rule above and are not a guess:\n"
    "- Each one is a real child, adult or toy, not a stock character. "
    "Colour them using exactly the description given for them below, for "
    "every part of them it describes, and nowhere else in the picture.\n"
    "- Getting a real person's hair, eyes or skin the wrong colour is not a "
    "small mistake: a picture of a child coloured with someone else's "
    "colouring is not a picture of that child.\n"
    "- Never substitute a generic or stereotypical colouring for any of "
    "them, and never lighten hair or skin towards a default."
)

# Nothing is recorded for a character saved before this feature existed, or
# whose parent has not yet corrected an automatic guess. There is nothing
# specific to tell the model about them, but the failure this whole rule
# exists to stop — defaulting to fair skin and blonde hair — is exactly the
# gap this line is here to close for those characters too.
UNDESCRIBED_CHARACTER_RULE = (
    "- No colouring is recorded yet for: {names}. Give them warm, natural "
    "colouring, and do not default to fair skin or blonde hair."
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


def _spliced(text: str) -> str:
    """Indent a constant to the templates' four-space margin before splicing it in.

    A multi-line constant inserted flush left defeats ``dedent()``'s common-prefix
    calculation below, so it stops stripping the margin from every other line —
    Scene, Style profile and the rest come out with a literal four-space indent
    the drawing service would actually receive. Caught in review on 2026-08-31
    by diffing composed prompts before and after the constants were spliced in.
    """
    return indent(text, "    ")


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
{_spliced(VISUAL_RULES)}

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
{_spliced(VISUAL_RULES)}

    Style profile: {style.instruction}
    Reader profile: {level.regions}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    Composition profile: {target_rule}
    """

    return dedent(prompt).strip()


def build_colour_suggestion_prompt(
    characters: Sequence[tuple[str, str]] = (),
) -> str:
    """Ask for a coloured version of the same drawing, as a guide to copy.

    The printable page stays black and white. This is a picture of what the
    finished thing could look like, for a child deciding what colour water,
    grass or a dinosaur's back should be.

    `characters` is (name, appearance) for whoever the picture was actually
    drawn with, read from the artwork's own recorded cast rather than
    whichever characters happen to be ticked when this is pressed. A
    picture drawn with nobody in it — an ordinary idea, or a sample — is
    passed nothing here, and colours exactly as it always has: sky blue,
    grass green, with no character rule appended at all.
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

    described = [
        (name.strip(), appearance.strip())
        for name, appearance in characters
        if name.strip() and appearance.strip()
    ]
    undescribed = [
        name.strip()
        for name, appearance in characters
        if name.strip() and not appearance.strip()
    ]

    if described or undescribed:
        lines = [f"- {name}: {appearance}" for name, appearance in described]
        if undescribed:
            lines.append(
                UNDESCRIBED_CHARACTER_RULE.format(names=", ".join(undescribed))
            )
        block = CHARACTER_COLOUR_RULE + "\n" + "\n".join(lines)
        prompt += f"\n{_spliced(block)}\n"

    return dedent(prompt).strip()


def build_character_scene_prompt(
    concept: str,
    characters: Sequence[tuple[str, str, str, str]],
    *,
    age_profile: str = "2-3 years",
    style_name: str = "Toddler bold",
    target: str = "A4 page",
    extra_instructions: str = "",
    variation_brief: str = "",
) -> str:
    """A scene starring saved characters, drawn from their reference pictures.

    `characters` is (name, kind, marks, appearance) in the same order the
    reference pictures are attached, because that order is the only thing
    telling the model which face is which. `appearance` is what a model
    saw in the photograph the one time it was asked — hair, eyes, skin and
    the like — read out here so a black-and-white drawing still carries the
    right hair length and texture even though it has no colour to lose. A
    character saved before that field existed carries an empty string.
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

    # One picture per character, in the order app.py attaches them, and the
    # ordinal is the only thing telling the model which face belongs to which
    # name.
    introductions = []
    for index, (name, kind, marks, appearance) in enumerate(characters):
        ordinal = ORDINALS[index] if index < len(ORDINALS) else f"number {index + 1}"
        article = _KIND_ARTICLES.get(kind, "character")
        line = f"The {ordinal} picture is Doodle's drawing of {name}, a {article}."
        if marks.strip():
            line += f" {marks.strip()}"
        if appearance.strip():
            line += f" {appearance.strip()}"
        introductions.append(line)

    likeness_block = _spliced(CHARACTER_LIKENESS_RULE)
    likeness_block += "\n\n" + _spliced(PORTRAIT_MATCH_RULE)
    if any(kind == "toy" for _, kind, _, _ in characters):
        likeness_block += "\n\n" + _spliced(TOY_LIKENESS_RULE)
    if any(kind == "character" for _, kind, _, _ in characters):
        likeness_block += "\n\n" + _spliced(NAMED_CHARACTER_RULE)

    # The face exemption goes after the profile lines rather than before them.
    # Proved on 2026-08-31 by drawing the same scene both ways with the same
    # two photographs: stated first, it was overruled by the four simplifying
    # profile lines that followed it and both girls came back as the same
    # stock cartoon child; stated last, they came back as themselves.
    people = sum(1 for _, kind, _, _ in characters if kind == "person")
    closing = ""
    if people:
        exemption = f"{FACE_DETAIL_EXEMPTION} {GENERIC_FACE_REFUSAL}"
        if people > 1:
            exemption += f" {TOLD_APART_RULE}"
        closing += "\n" + _spliced(exemption) + "\n"
    closing += "\n" + _spliced(CAST_FOREGROUND_RULE) + "\n"

    prompt = f"""
    Create an original black-and-white colouring-book illustration for {level.reader}.

    Scene: {scene}

    Who is in it:
{_spliced(chr(10).join(introductions))}

{likeness_block}

    Visual rules:
{_spliced(VISUAL_RULES)}

    Style profile: {style.instruction}
    Reader profile: {level.regions}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    Composition profile: {target_rule}
{closing}
    """

    if extra_instructions.strip():
        prompt += f"\nAdditional direction: {extra_instructions.strip()}\n"

    return dedent(prompt).strip()


def build_caricature_prompt(
    name: str,
    kind: str,
    marks: str,
    appearance: str = "",
    *,
    age_profile: str = "6-9 years",
) -> str:
    """A head-and-shoulders caricature, composed for a round badge.

    The default level is 6-9 rather than the toddler default because a
    caricature is nothing but a face, so the detail belongs everywhere.
    `appearance` is what a model saw in the reference photograph — hair,
    eyes, skin and the like — carried into the same introduction sentence
    as `marks` so the caricature keeps the right hair length and texture
    even though it is drawn in black and white.
    """

    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS["6-9 years"])
    subject = _KIND_ARTICLES.get(kind, "character")
    marks_line = f" {marks.strip()}" if marks.strip() else ""
    appearance_line = f" {appearance.strip()}" if appearance.strip() else ""

    likeness_block = _spliced(CHARACTER_LIKENESS_RULE)
    if kind == "toy":
        likeness_block += "\n\n" + _spliced(TOY_LIKENESS_RULE)
    elif kind == "character":
        likeness_block += "\n\n" + _spliced(NAMED_CHARACTER_RULE)

    prompt = f"""
    Create an original black-and-white colouring-book caricature.

    Subject: a good-natured caricature of {name}, the {subject} in the attached
    picture, head and shoulders only, facing forward.{marks_line}{appearance_line}

{likeness_block}

    Caricature direction: this is a seaside caricature, so exaggerate boldly and
    comically. Draw the head much larger than the body. Push the two or three
    most distinctive features far beyond life while keeping them unmistakably
    recognisable. Warm and affectionate, never unkind or ugly. A polite,
    accurate, flattering portrait is the wrong answer.

    Visual rules:
{_spliced(VISUAL_RULES)}

{_spliced(BADGE_CORNERS_RULE)}

    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    """

    return dedent(prompt).strip()
