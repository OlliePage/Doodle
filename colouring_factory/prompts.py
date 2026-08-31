from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from textwrap import dedent, indent


@dataclass(frozen=True)
class StylePreset:
    label: str
    instruction: str


# What KIND of picture, which is a different question from how detailed it is.
# There used to be four of these and two of them — "Toddler bold" and
# "Preschool detailed" — only restated the age setting beside them, badly and
# without its region counts. Worse, they could contradict it: choosing
# "Grown-up" and "Toddler bold" together sent one request saying both "only a
# few large regions" and "aim for 150 or more small colouring regions", and the
# model picked one. A settings file written on 2026-08-31 held exactly that
# pair. "Badge portrait" went the same way, asking for a subject composed
# inside a circle while the page target asked for A4; the "Draw it for a badge"
# button on the result screen does that job on a square canvas, properly.
#
# What is left answers only what the age setting cannot. DEFAULT_STYLE is
# first on purpose: an unrecognised saved style is coerced to whichever entry
# leads, so it has to be the one that changes nothing.
DEFAULT_STYLE = "A scene"

STYLE_PRESETS: dict[str, StylePreset] = {
    # No instruction at all. The age setting already carries region count, line
    # weight and texture at every rung, so a scene needs nothing added; the
    # builders omit the Style profile line entirely rather than sending a
    # labelled blank.
    DEFAULT_STYLE: StylePreset(label=DEFAULT_STYLE, instruction=""),
    "Just the things": StylePreset(
        label="Just the things",
        instruction=(
            "Draw one to three familiar objects, oversized and well separated, as "
            "simple closed shapes with almost no background."
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
        # Third wording. The first offered "a decorative border of repeating
        # motifs" and "patterned fills wherever a plain area would otherwise
        # sit" as ways to reach the count, and a grown-up portrait came back on
        # 2026-08-31 with a plain figure and a flowy ornamental background. The
        # second pointed the count at the subject and told the page to fill
        # corner to corner, and the same day a picnic under a hot air balloon
        # festival came back worse: the nine large balloons that were the whole
        # point of the toddler sheet shrank into wallpaper, bunting ran across
        # the top, and the foreground and both margins filled with daisies and
        # foliage the words never mentioned. Anyone would have taken the
        # toddler sheet.
        #
        # Three clauses paid for that. "Almost no empty white space" is an area
        # order that says nothing about what fills the area, and it contradicted
        # the visual rules' pure white background, the A4 profile's "leave
        # useful white space around it" and the badge rule's blank corners — so
        # the model followed the one instruction it could count. "Individual
        # leaves and petals" was the only example in the list that also works as
        # a free-standing object to multiply; you cannot scatter a fold, but you
        # can scatter a petal. And a count scored against the page is far
        # cheaper to reach by repeating a small shape forty times than by
        # subdividing nine large ones, so the balloons shrank to make room.
        #
        # The count now lives inside the objects and cannot be earned by adding
        # to the page. The border offer is gone rather than demoted, because a
        # field that overrides the shared visual rules teaches the model those
        # rules are negotiable immediately before it decides whether inventing a
        # meadow is allowed.
        regions=(
            "Aim for 150 or more small colouring regions, and find every one of "
            "them inside the things the picture already contains: regions won by "
            "adding something new do not count. Spend that detail on the subject "
            "first, and the subject is everything the description names, not only "
            "the people in it. Draw each named thing at the size the scene gives "
            "it, big enough to be looked at, then divide it into ten or twenty "
            "small closed shapes cut from what it is really made of: the seams "
            "and folds of cloth, the planks and grain of wood, the courses of a "
            "wall. Nothing may enter the picture that the description has not "
            "asked for and the scene does not need in order to stand up: a meadow "
            "of flowers nobody asked for, a run of bunting or a decorative border "
            "arriving to fill a gap is the failure this refuses. Nor may anything "
            "named be shrunk, or repeated small until it becomes wallpaper, to "
            "make room for one. Space the description does not account for is "
            "left white; a gap is not a place to put something. A simply drawn "
            "subject standing in an intricate setting is the wrong answer, and so "
            "is an ornamental background compensating for a plain one."
        ),
        line_rule=(
            "Fine, even outlines of consistent weight throughout, in the intricate "
            "style of an adult colouring book, mandala or zentangle."
        ),
        # The more direct cause of the flower mat than the region count was.
        # It named the motif (petals, leaves), nominated every empty area as
        # somewhere to put it — the sky is a larger area and so is the grass —
        # and declared ornament to be the goal rather than a consequence.
        # Pattern is still welcome and still dense; it is now bound to surfaces
        # that carry pattern in life, and the two places the wallpaper and the
        # daisies went are refused by name.
        texture_rule=(
            "Dense decorative pattern belongs wherever a surface really carries "
            "one — a printed dress, a tiled floor, a brick wall, the scales of a "
            "fish, the weave of a basket — and nowhere else: empty sky, bare "
            "ground and the space between things stay plain. Every mark of it "
            "must be a closed shape a fine pen or pencil can colour, never a "
            "shaded or filled black mass. Density here means more regions to "
            "colour, never darker drawing: no hatching, no cross-hatching, no "
            "stippling and no strokes standing in for texture."
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
    "The attached pictures are the reference for how the subjects of this "
    "drawing really look. Draw each one as a friendly cartoon who is "
    "unmistakably recognisable "
    "as that particular one rather than a generic example. Follow each one's "
    "real face shape and their real hair length, parting and wave. Draw the "
    "hair as its outline plus closed wave and lock shapes inside it — a few "
    "large ones on a simple page, many smaller ones on a detailed one — and "
    "never as separate fine strands, flyaway wisps or hairline texture, "
    "however wispy the reference is and however detailed the page. Hair drawn "
    "as strokes is a black mass nobody can colour. Show markings, worn "
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
# The likeness has to stop at the head. An earlier version of this asked for
# every particular thing the drawing showed, "down to a hair clip or a pattern
# on a top", and a saved character wearing a flowery dress then wore it in
# every picture at every age setting: a toddler page came back with roughly
# forty separate flowers on one dress, each far too small for a crayon, while
# the rest of the page obeyed the toddler rules perfectly. A character whose
# outfit is complicated makes every drawing of them complicated, however simple
# the setting asks for. Proved on 2026-08-31 by drawing the same fox scene both
# ways: the same girl came back in plain dungarees, still recognisably herself.
PORTRAIT_MATCH_RULE = (
    "Each attached picture is the line drawing Doodle has already made of that "
    "character and shows their family. It is the authority on who they are. "
    "Take from it the face \u2014 the shape of the eyes, the nose, the mouth, "
    "the eyebrows \u2014 along with the hair and anything worn on the head, "
    "such as glasses or a hair clip, so that the character in your picture and "
    "the character in that drawing are plainly the same one drawn twice, not "
    "two who look similar. Their clothes are not part of who they are: dress "
    "them for the scene, and draw whatever they wear the way the reader "
    "profile demands. A patterned top in the drawing must not become a "
    "patterned top in your picture unless the reader profile allows pattern."
)

# The portrait a character is drawn from is one forward-facing smile, and
# nothing told the model that only the face was being copied. So every scene
# came back with the same expression at the same angle whatever was happening
# in it, which reads as unsettling rather than familiar. Confirmed on
# 2026-08-31: with this rule a girl asked to look out to sea shaded her eyes
# and turned three quarters away, and her sister knelt side-on to dig, both
# still plainly themselves.
POSE_FREEDOM_RULE = (
    "The attached picture tells you who they are, not how they are standing. "
    "Take their face, hair and features from it; take their pose, their "
    "expression and the direction they are looking from the scene. Draw them "
    "from whatever angle the action calls for \u2014 in profile, three "
    "quarters, from behind, looking up, looking away \u2014 and wearing "
    "whatever expression fits what they are doing, whether that is laughing, "
    "concentrating, shouting or thinking. Repeating the reference's "
    "forward-facing smile in every picture makes them look like a doll rather "
    "than a person."
)

# The scene builder's other reference is a portrait Doodle drew, and
# PORTRAIT_MATCH_RULE says so in as many words. A picture dropped onto the page
# is a photograph, or somebody else's drawing, and telling the model it is
# Doodle's own line drawing would be a plain lie about what it is looking at.
#
# The clothing instruction is deliberately the opposite of the portrait rule's.
# A saved character recurs across many pictures, so their outfit is not part of
# who they are and PORTRAIT_MATCH_RULE dresses them for the scene instead. A
# dropped picture is used once and whatever it shows is the subject, jumper
# and all — a parent who drops a photograph of a teddy in a knitted waistcoat
# wants the waistcoat.
DROPPED_PICTURE_RULE = (
    "That picture is a photograph or a drawing the reader has supplied, not a "
    "drawing Doodle made. What it shows is the subject of this picture: read "
    "its shape, its markings, its wear and everything else that makes it that "
    "particular one rather than a generic example, and draw that same thing "
    "into the scene described above. Keep what it is wearing or carrying if "
    "that is part of how it is recognised. Do not copy the photograph's "
    "background, its lighting or its framing, and do not trace its edges: "
    "draw the thing it shows, freshly, as a colouring-book illustration."
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
# child different from another.
#
# The first attempt at this over-corrected, demanding every head be at least a
# fifth of the page and telling the face exemption to draw heads larger than
# proportion allows. Every child then came back with the same oversized head at
# the same distance, page after page — a nodding doll rather than a person. So
# it asks for closeness and leaves the amount to the scene, and says plainly
# that heads are a normal size.
CAST_FOREGROUND_RULE = (
    "Composition note for whoever the attached pictures show: draw them near "
    "enough to the viewer that their faces read clearly, and let the action "
    "decide how near. "
    "Their heads are an ordinary size for their bodies and are never enlarged. "
    "A wide shot of small full-length figures lost in a landscape is the wrong "
    "answer, and so is a head too big for the body it is on."
)

# A face is small on a page and carries all of the recognition, so it gets its
# own allowance while the rest of the sheet stays colourable. Without this, a
# face at the toddler level comes back as a stock cartoon child wearing the
# reference's glasses; with it, the same page keeps its big simple trees.
FACE_DETAIL_EXEMPTION = (
    "Detail exception, which overrides the reader profile for one part of the "
    "picture only: each person's head — the face, the hair and the glasses — may "
    "carry as much fine line work as it takes to be recognisably them. "
    "Everything else in the picture, including bodies, clothes and the whole "
    "setting, obeys the reader profile exactly, whatever that profile asks for. "
    "Clothing is part of everything else: a dress at the toddler "
    "level is two or three large plain shapes, however patterned it was in the "
    "reference, and on a detailed page it carries as many small closed shapes "
    "as that profile demands."
)

# "Person" and "toy" each need their own instruction because they fail in
# opposite directions: a face gets smoothed into a generic child (the
# exemption above), while a toy gets tidied into a fresh one from a shop
# shelf, losing the exact wear that makes it that toy. "Character" is a third
# thing again — an existing design, not a real object — so it needs telling
# to keep that design rather than reinterpreting the idea of it.
# "Object" is the fourth and is not a fourth kind of character: it is a table,
# a kettle, a bicycle. It exists because the caricature builder's face wording
# — head and shoulders, facing forward, the head drawn much larger than the
# body — means nothing for furniture, and because a table introduced as a
# "character" invites the model to give it a face.
_KIND_ARTICLES = {
    "person": "person",
    "toy": "toy",
    "character": "character",
    "object": "object",
}

# A seaside artist enlarges the head because the head is where one sitter
# stops looking like every other sitter, and draws the body small because that
# is where everybody is alike. A table has no head, but it has the same
# division: the ring-scarred top, the one replaced leg, the low squat height
# are where this table stops being a catalogue table. That is what gets pushed.
OBJECT_CARICATURE_RULE = (
    "This is a seaside caricature of a thing rather than a person, so find "
    "what makes this particular one different from every other one of its kind "
    "and push it far beyond life: a lean, a sag, a wonky leg, a worn corner, a "
    "squat or spindly proportion, whatever is most itself about it. Draw "
    "everything it shares with every other one of its kind small, plain and "
    "quickly. Give it presence and a bit of attitude through proportion, angle "
    "and stance. Warm and affectionate, never mocking. A neat, accurate, "
    "catalogue drawing is the wrong answer."
)

# The failure this refuses is the one already recorded twice for children: a
# stock cartoon face landing on every subject, so that the particular thing
# photographed stops being what the drawing is about. A face that is really
# there — a teddy's stitched one, a mug's printed one — is kept and exaggerated
# like any other feature, because the rule is about invention, not about faces.
NO_INVENTED_FACE_RULE = (
    "Do not give it eyes, a mouth or a face it does not already have, and do "
    "not stand it up on legs or give it arms. If the real thing has a face, "
    "keep that face and exaggerate it along with everything else. Its "
    "character comes from how it is drawn, not from being turned into a "
    "cartoon creature."
)

# BADGE_CORNERS_RULE's refusals, minus its final circle bullet — the one a
# wide subject cannot obey. The bluntness is the part that was proved, so it is
# repeated rather than split into a shared head and two tails.
# TOY_LIKENESS_RULE generalised off the toy shelf. CHARACTER_LIKENESS_RULE
# cannot be used here: it asks for real face shape, real hair length, parting
# and wave, and freckles, none of which a table has.
OBJECT_LIKENESS_RULE = (
    "The attached picture is the reference for what this thing really looks "
    "like. Draw this exact one rather than a new one from a shop: keep its "
    "wear, its scratches, its stains, its repairs and anything odd or "
    "mismatched about it exactly as it really is, rather than tidying them "
    "away. Show marks and worn patches as outlined shapes to colour, never as "
    "shading."
)

# The reader profile's region count is written for a scene, and at 6-9 it asks
# outright for "a real setting around the subject, with foreground and
# background" — which the framing rule above has just refused. A caricature has
# no setting, so the count has to be pointed at the only thing on the page.
CARICATURE_DENSITY_RULE = (
    "That region count applies to the subject alone. There is no setting here "
    "to spend it on, so subdivide the subject itself until the count is met, "
    "and leave the space around it empty."
)

OBJECT_FRAMING_RULE = (
    "Draw the whole thing, from the angle that shows most of what makes it "
    "that one. Draw NOTHING around it: no background, no scenery, no room, no "
    "surface it stands on, no border, no frame. Leave generous clear white "
    "space on every side of it."
)

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


def _style_line(style: StylePreset) -> str:
    """The Style profile line, or nothing at all.

    "A scene" carries no instruction, because the age setting already says
    everything a plain scene needs. Splicing an empty instruction into the
    template would send the model the line "Style profile:" with nothing after
    it, which is a labelled blank rather than an absence.
    """

    instruction = style.instruction.strip()
    return f"    Style profile: {instruction}\n" if instruction else ""


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
    style_name: str = DEFAULT_STYLE,
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

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS[DEFAULT_STYLE])
    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS[DEFAULT_LEVEL])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    prompt = f"""
    Create an original black-and-white colouring-book illustration for {level.reader}.

    Scene: {scene}

    Visual rules:
{_spliced(VISUAL_RULES)}

{_style_line(style)}    Reader profile: {level.regions}
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
    style_name: str = DEFAULT_STYLE,
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

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS[DEFAULT_STYLE])
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

{_style_line(style)}    Reader profile: {level.regions}
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
    dropped_appearance: str | None = None,
    age_profile: str = "2-3 years",
    style_name: str = DEFAULT_STYLE,
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

    `dropped_appearance` is None when nothing was dropped onto the page. When
    a picture was dropped it holds that picture's description, which may be an
    empty string if the one vision call it takes failed. A dropped picture is
    always the last one attached, after every character's portrait, so its
    ordinal here has to match the order app.py builds the reference tuple in.
    Either a cast or a dropped picture is enough on its own.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if not characters and dropped_appearance is None:
        raise ValueError("At least one character or a dropped picture is required.")

    scene = variation_brief.strip() or concept
    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS[DEFAULT_STYLE])
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

    # Always last, matching the order app.py attaches the pictures: every
    # character's portrait first, the dropped picture after them. The ordinal
    # words are the only thing binding a picture to what it shows, so the two
    # orders cannot be allowed to drift apart.
    if dropped_appearance is not None:
        index = len(characters)
        ordinal = ORDINALS[index] if index < len(ORDINALS) else f"number {index + 1}"
        line = (
            f"The {ordinal} picture is one the reader dropped onto the page. "
            "What it shows is the subject of this drawing."
        )
        if dropped_appearance.strip():
            line += f" {dropped_appearance.strip()}"
        introductions.append(line)

    likeness_block = _spliced(CHARACTER_LIKENESS_RULE)
    # Only when there is a cast: this rule asserts the attached picture is a
    # line drawing Doodle already made, which is false of a dropped photograph.
    if characters:
        likeness_block += "\n\n" + _spliced(PORTRAIT_MATCH_RULE)
    if dropped_appearance is not None:
        likeness_block += "\n\n" + _spliced(DROPPED_PICTURE_RULE)
    likeness_block += "\n\n" + _spliced(POSE_FREEDOM_RULE)
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
    # A dropped picture always earns the exemption, because Doodle has no idea
    # whether it shows a child or a teddy and the two fail in opposite
    # directions. Spending it on a toy costs nothing — a toy has no face to
    # genericise, which the caricature evidence already established — while
    # withholding it from a photograph of a child gives back the stock cartoon
    # this rule exists to refuse.
    if people or dropped_appearance is not None:
        exemption = f"{FACE_DETAIL_EXEMPTION} {GENERIC_FACE_REFUSAL}"
        # Still counted on the named cast alone: two saved characters have to
        # be told apart from each other, and one dropped picture has nobody to
        # be confused with.
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

{_style_line(style)}    Reader profile: {level.regions}
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

    The reader profile is carried through as well as the line and detail ones.
    Without it, choosing "Grown-up" for a portrait changed the line weight and
    permitted pattern but never asked for more to be drawn — the word "regions"
    did not appear in the prompt at all — so the face came back as simple as a
    toddler's with an intricate background behind it. Reported 2026-08-31.
    `appearance` is what a model saw in the reference photograph — hair,
    eyes, skin and the like — carried into the same introduction sentence
    as `marks` so the caricature keeps the right hair length and texture
    even though it is drawn in black and white.
    """

    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS["6-9 years"])
    subject = _KIND_ARTICLES.get(kind, "character")
    marks_line = f" {marks.strip()}" if marks.strip() else ""
    appearance_line = f" {appearance.strip()}" if appearance.strip() else ""

    if kind == "object":
        likeness_block = _spliced(OBJECT_LIKENESS_RULE)
        likeness_block += "\n\n" + _spliced(NO_INVENTED_FACE_RULE)
    else:
        likeness_block = _spliced(CHARACTER_LIKENESS_RULE)
        if kind == "toy":
            likeness_block += "\n\n" + _spliced(TOY_LIKENESS_RULE)
        elif kind == "character":
            likeness_block += "\n\n" + _spliced(NAMED_CHARACTER_RULE)

    # An object is drawn whole and framed for a page; a face is drawn head and
    # shoulders and framed for a badge. Everything else about the two is the
    # same request, which is why this branches rather than forking a sixth
    # builder and giving the colouring-book contract a sixth place to drift.
    if kind == "object":
        named = f"{name.strip()}, the " if name.strip() else "the "
        subject_line = (
            f"    Subject: a good-natured caricature of {named}{subject} in the "
            f"attached picture, drawn whole."
            f"{marks_line}{appearance_line}"
        )
        direction_block = f"    Caricature direction: {OBJECT_CARICATURE_RULE}"
        framing_block = _spliced(OBJECT_FRAMING_RULE)
    else:
        subject_line = (
            f"    Subject: a good-natured caricature of {name}, the {subject} in "
            f"the attached picture, head and shoulders only, facing "
            f"forward.{marks_line}{appearance_line}"
        )
        direction_block = (
            "    Caricature direction: this is a seaside caricature, so exaggerate "
            "boldly and comically. Draw the head much larger than the body. Push "
            "the two or three most distinctive features far beyond life while "
            "keeping them unmistakably recognisable. Warm and affectionate, never "
            "unkind or ugly. A polite, accurate, flattering portrait is the wrong "
            "answer."
        )
        framing_block = _spliced(BADGE_CORNERS_RULE)

    prompt = f"""
    Create an original black-and-white colouring-book caricature.

{subject_line}

{likeness_block}

{direction_block}

    Visual rules:
{_spliced(VISUAL_RULES)}

{framing_block}

    Reader profile: {level.regions}
{_spliced(CARICATURE_DENSITY_RULE)}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    """

    return dedent(prompt).strip()
