import pytest

from colouring_factory.prompts import (
    BADGE_CORNERS_RULE,
    CAST_FOREGROUND_RULE,
    DETAIL_LEVELS,
    DROPPED_PICTURE_RULE,
    POSE_FREEDOM_RULE,
    FACE_DETAIL_EXEMPTION,
    GENERIC_FACE_REFUSAL,
    NAMED_CHARACTER_RULE,
    TOLD_APART_RULE,
    TOY_LIKENESS_RULE,
    build_caricature_prompt,
    build_character_scene_prompt,
    build_colouring_prompt,
)


def test_each_character_is_named_and_matched_to_its_picture() -> None:
    prompt = build_character_scene_prompt(
        "building a sandcastle",
        [
            ("Ida", "person", "Curly hair, round glasses.", ""),
            ("Bear", "toy", "A bald patch on one ear.", ""),
        ],
    )

    assert "Ida" in prompt and "Bear" in prompt
    assert "Curly hair, round glasses." in prompt
    assert "A bald patch on one ear." in prompt
    # The order the pictures are attached in is the only thing telling the model
    # which face is which, so the prompt has to say so.
    assert "first" in prompt.lower() and "second" in prompt.lower()


def test_the_ordinal_naming_each_character_matches_their_actual_order() -> None:
    """The docstring calls this order "the only thing telling the model
    which face is which": reference pictures are attached in the order
    `characters` lists them, so the ordinal word introducing each one has to
    name the same character its picture actually is. The previous test only
    checks that "first" and "second" both appear somewhere in the prompt,
    which would still pass if the mapping were reversed and two characters
    swapped likenesses silently."""

    prompt = build_character_scene_prompt(
        "building a sandcastle",
        [
            ("Ida", "person", "Curly hair, round glasses.", ""),
            ("Bear", "toy", "A bald patch on one ear.", ""),
        ],
    )

    assert "The first picture is Doodle's drawing of Ida" in prompt
    assert "The second picture is Doodle's drawing of Bear" in prompt


def test_a_person_gets_the_face_exemption_and_a_toy_does_not() -> None:
    """A face at toddler detail comes back as a generic child.

    Proved on 2026-08-30: the same scene drawn with and without this exemption
    gave a stock cartoon face and a recognisable one. A toy needs no such rule,
    because a toy has no face for a model to smooth away.
    """

    with_person = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.", "")]
    )
    toy_only = build_character_scene_prompt(
        "having a picnic", [("Bear", "toy", "A bald patch on one ear.", "")]
    )

    assert FACE_DETAIL_EXEMPTION in with_person
    assert FACE_DETAIL_EXEMPTION not in toy_only


def test_hair_keeps_its_real_shape_without_becoming_fine_strands() -> None:
    """Both halves of this rule were paid for.

    Strands a pixel wide can break in the despeckle pass, which is why fine
    hairline texture is still refused. But the earlier version went further and
    flattened all hair into "one or two large closed shapes", and hair length
    and parting are most of what tells one child from another at a glance —
    erasing them was part of why every drawn child came back the same. So the
    rule now has to ask for the real shape AND refuse the fine strands, and
    this test fails if either half goes missing.
    """

    prompt = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.", "")]
    )
    assert "real hair length, parting and wave" in prompt
    assert "never as separate fine strands" in prompt
    # The refusal has to survive a detailed page as well as a simple one. The
    # density rule used to ask for "strands" by name while this rule banned
    # them, and on 2026-08-31 a Grown-up drawing resolved that fight the wrong
    # way: hair came back as a black mass of strokes nobody could colour.
    detailed = build_character_scene_prompt(
        "walking in a forest",
        [("Ida", "person", "", "")],
        age_profile="Grown-up",
    )
    assert "never as separate fine strands" in detailed
    assert "however wispy the reference is and however detailed the page" in detailed
    assert "strands" not in DETAIL_LEVELS["Grown-up"].regions, (
        "the density rule is asking for the very thing the likeness rule refuses"
    )


def test_the_face_exemption_is_read_after_the_rules_it_overrides() -> None:
    """Stated first, the exemption was overruled by what came after it.

    Proved on 2026-08-31 with six drawings of the same two real children. The
    exemption claims to override the reader profile, and while it appeared
    ABOVE that profile the model followed whichever simplifying line it read
    last: both girls came back as the same stock cartoon child. Moving it below
    the four profile lines is the whole of the fix, so position, not presence,
    is what this test guards.
    """

    prompt = build_character_scene_prompt(
        "walking in a forest",
        [("Ida", "person", "Curly hair.", ""), ("Mo", "person", "Freckles.", "")],
    )

    exemption_at = prompt.index(FACE_DETAIL_EXEMPTION)
    for overridden in ("Reader profile:", "Line profile:", "Detail profile:"):
        assert prompt.index(overridden) < exemption_at, (
            f"{overridden} is read after the exemption that claims to override it"
        )


def test_named_characters_are_drawn_close_enough_to_be_recognised() -> None:
    """A likeness needs pixels before it needs wording.

    Asked for a walk in a forest, the model drew three full-length figures in a
    landscape and gave each head about a ninth of the page's height. At that
    size no instruction can carry a face, so the composition itself has to
    change.
    """

    for cast in (
        [("Ida", "person", "Curly hair.", "")],
        [("Bear", "toy", "A bald patch on one ear.", "")],
        [("Ida", "person", "", ""), ("Bear", "toy", "", "")],
    ):
        prompt = build_character_scene_prompt("walking in a forest", cast)
        assert CAST_FOREGROUND_RULE in prompt
        assert prompt.index("Composition profile:") < prompt.index(
            CAST_FOREGROUND_RULE
        ), "the override must be read after the profile it overrides"


def test_two_people_are_told_to_be_distinguishable_and_one_is_not() -> None:
    """Asking a single subject not to look like the others reads as nonsense,
    so the sentence only appears once there is someone to be confused with."""

    two = build_character_scene_prompt(
        "walking in a forest",
        [("Ida", "person", "Curly hair.", ""), ("Mo", "person", "Freckles.", "")],
    )
    one = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.", "")]
    )
    toy = build_character_scene_prompt(
        "having a picnic", [("Bear", "toy", "A bald patch.", "")]
    )

    assert TOLD_APART_RULE in two
    assert TOLD_APART_RULE not in one
    assert GENERIC_FACE_REFUSAL in one, "one child can still be drawn generically"
    assert GENERIC_FACE_REFUSAL not in toy, "a teddy is not a cartoon child"


def test_a_doodle_with_no_characters_still_builds() -> None:
    """The ordinary path has no cast, and a template variable that only exists
    on the cast path once leaked into it — every plain drawing would have
    raised NameError before a single picture was requested."""

    prompt = build_colouring_prompt("a blue dinosaur on a skateboard")
    assert "a blue dinosaur on a skateboard" in prompt
    assert "{" not in prompt, "an unsubstituted template variable survived"


def test_the_colouring_book_contract_survives() -> None:
    prompt = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.", "")]
    )
    assert "Pure white background." in prompt
    assert "Black line work only" in prompt


def test_a_caricature_refuses_the_corners_and_asks_for_exaggeration() -> None:
    prompt = build_caricature_prompt("Ida", "person", "Curly hair, round glasses.")

    assert BADGE_CORNERS_RULE in prompt
    assert "Draw NOTHING in the corners" in prompt
    # A polite, flattering portrait was the first attempt's failure, so the
    # prompt names it as the wrong answer.
    assert "wrong answer" in prompt


def test_a_toy_and_a_named_character_get_different_prompts() -> None:
    """FB-13: "A toy" and "Something else" used to produce byte-identical
    prompts, and characters.py's own comment claimed a toy got its own
    rules describing code that was never written."""

    toy = build_character_scene_prompt("a picnic", [("Bear", "toy", "A bald ear.", "")])
    character = build_character_scene_prompt(
        "a picnic", [("Bear", "character", "A bald ear.", "")]
    )

    assert toy != character
    assert TOY_LIKENESS_RULE in toy
    assert TOY_LIKENESS_RULE not in character
    assert NAMED_CHARACTER_RULE in character
    assert NAMED_CHARACTER_RULE not in toy
    # The article naming what Bear is must not collapse toy and character
    # into the same word either.
    assert "a toy." in toy
    assert "a character." in character


def test_a_toy_and_a_named_character_caricature_also_differ() -> None:
    toy = build_caricature_prompt("Bear", "toy", "A bald ear.")
    character = build_caricature_prompt("Bear", "character", "A bald ear.")

    assert toy != character
    assert TOY_LIKENESS_RULE in toy
    assert NAMED_CHARACTER_RULE in character
    assert TOY_LIKENESS_RULE not in character
    assert NAMED_CHARACTER_RULE not in toy


def test_a_scene_with_no_characters_is_refused() -> None:
    with pytest.raises(ValueError):
        build_character_scene_prompt("walking in a forest", [])


def test_no_composed_line_is_left_ragged() -> None:
    """A multi-line rule constant spliced in flush left defeats dedent()'s
    common-prefix calculation, so the rest of the prompt keeps a literal
    four-space indent it should have lost. Caught in review on 2026-08-31 by
    diffing composed prompts before and after VISUAL_RULES was introduced."""

    scene = build_character_scene_prompt(
        "building a sandcastle",
        [
            ("Ida", "person", "Curly hair, round glasses.", "Brown eyes, dark hair."),
            ("Bear", "toy", "A bald patch on one ear.", "A red ribbon."),
        ],
    )
    caricature = build_caricature_prompt(
        "Ida", "person", "Curly hair, round glasses.", "Brown eyes, dark hair."
    )

    for prompt in (scene, caricature):
        for line in prompt.splitlines():
            assert not line[:1].isspace(), f"ragged line: {line!r}"


def test_a_scene_carries_each_characters_recorded_appearance() -> None:
    """The bug this whole feature exists for: a black-and-white drawing has
    no colour of its own to lose, but it still has to carry hair length and
    texture, so the same words that will later fix the colouring also fix
    the line art."""

    prompt = build_character_scene_prompt(
        "building a sandcastle",
        [
            (
                "Ida",
                "person",
                "Round glasses.",
                "Brown eyes, wavy dark-brown hair to her shoulders, light-brown skin.",
            )
        ],
    )
    assert "wavy dark-brown hair to her shoulders" in prompt


def test_a_caricature_carries_the_recorded_appearance_too() -> None:
    prompt = build_caricature_prompt(
        "Ida",
        "person",
        "Round glasses.",
        "Brown eyes, wavy dark-brown hair to her shoulders, light-brown skin.",
    )
    assert "wavy dark-brown hair to her shoulders" in prompt


def test_a_blank_appearance_adds_nothing_to_either_prompt() -> None:
    """A character added before this field existed, or one whose parent has
    not filled it in, must draw exactly as it always did — no stray blank
    sentence, no double space, no crash."""

    with_blank = build_character_scene_prompt(
        "a picnic", [("Bear", "toy", "A bald ear.", "")]
    )
    assert "  " not in with_blank

    caricature_blank = build_caricature_prompt("Bear", "toy", "A bald ear.", "")
    caricature_default = build_caricature_prompt("Bear", "toy", "A bald ear.")
    assert caricature_blank == caricature_default
    assert "  " not in caricature_blank


def test_heads_are_never_asked_to_be_bigger_than_they_should_be() -> None:
    """The first attempt at making faces recognisable over-corrected.

    It told the face exemption to draw heads larger than proportion allows and
    demanded every head fill a fifth of the page, so every child came back with
    the same oversized head at the same distance, page after page. A parent
    called it a nodding doll, and was right.
    """

    prompt = build_character_scene_prompt(
        "surfing next to dolphins", [("Ida", "person", "Curly hair.", "")]
    )

    assert "larger in the frame than realistic proportion" not in prompt
    assert "one fifth of the picture" not in prompt
    assert "ordinary size for their bodies and are never enlarged" in prompt


def test_the_drawing_fixes_who_they_are_and_the_scene_fixes_the_pose() -> None:
    """A character is stored as one forward-facing smile.

    Nothing said only the face was being copied, so that smile turned up at
    that angle in every picture whatever was happening. Confirmed fixed on
    2026-08-31: a girl asked to look out to sea shaded her eyes and turned
    three quarters away while her sister knelt side-on to dig, both still
    plainly themselves.
    """

    prompt = build_character_scene_prompt(
        "building a sandcastle",
        [("Ida", "person", "", ""), ("Bo", "toy", "", "")],
    )

    assert POSE_FREEDOM_RULE in prompt
    # The two halves of the rule, either of which alone leaves the doll.
    assert "tells you who they are, not how they are standing" in prompt
    assert (
        "take their pose, their expression and the direction they are looking" in prompt
    )


def test_a_characters_clothes_obey_the_age_setting_not_the_portrait() -> None:
    """A complicated outfit would otherwise make every drawing complicated.

    The rule once asked for every particular thing the stored drawing showed,
    down to a pattern on a top. A girl saved in a flowery dress then wore it at
    every age setting, and a toddler page came back with about forty separate
    flowers on one dress, each far too small for a crayon, while the rest of
    the page obeyed the toddler rules perfectly.
    """

    prompt = build_character_scene_prompt(
        "petting a baby fox", [("Ida", "person", "", "")]
    )

    assert "down to a hair clip or a pattern on a top" not in prompt
    assert "Their clothes are not part of who they are" in prompt
    assert "must not become a patterned top" in prompt
    assert "a dress at the toddler level is two or three large plain shapes" in prompt


def test_the_face_exemption_still_covers_only_the_head() -> None:
    """The exemption is what makes a likeness possible, and also the thing most
    likely to leak into the rest of the page if it is ever loosened."""

    prompt = build_character_scene_prompt(
        "petting a baby fox", [("Ida", "person", "", "")]
    )

    exemption = prompt[prompt.index("Detail exception") :]
    head_words = exemption[: exemption.index("Everything else")]
    assert "the face, the hair and the glasses" in head_words
    for elsewhere in ("dress", "clothes", "trousers", "shoes"):
        assert elsewhere not in head_words, (
            f"{elsewhere} has crept into the part of the page allowed fine detail"
        )


# --- a picture dropped onto the page -------------------------------------
#
# A dropped picture is a character nobody saved: it supplies identity, the
# typed words supply the scene. These tests pin the two things that make that
# work — the model being told what the picture actually is, and the picture
# being introduced in the same position app.py attaches it.


def test_a_dropped_picture_is_introduced_last() -> None:
    """The ordinal words are the only thing binding a picture to what it
    shows, so the order here and the order app.py attaches the bytes in have
    to agree. The cast's portraits go first, the dropped picture after them."""

    prompt = build_character_scene_prompt(
        "riding a rocket",
        [("Ida", "person", "", ""), ("Bear", "toy", "", "")],
        dropped_appearance="A knitted rabbit with one ear turned down.",
    )

    assert "The first picture is Doodle's drawing of Ida" in prompt
    assert "The second picture is Doodle's drawing of Bear" in prompt
    assert "The third picture is one the reader dropped onto the page" in prompt
    assert "A knitted rabbit with one ear turned down." in prompt


def test_a_dropped_picture_needs_no_cast() -> None:
    """Dropping a picture and typing nothing else is the whole point of the
    feature, so an empty cast must not raise."""

    prompt = build_character_scene_prompt(
        "a knitted rabbit having a picnic", [], dropped_appearance=""
    )

    assert "The first picture is one the reader dropped onto the page" in prompt


def test_neither_a_cast_nor_a_dropped_picture_is_refused() -> None:
    with pytest.raises(ValueError):
        build_character_scene_prompt("a rabbit", [])


def test_a_dropped_picture_is_never_called_a_doodle_drawing() -> None:
    """PORTRAIT_MATCH_RULE asserts the reference is a line drawing Doodle
    already made. Said about a photograph it is a plain lie about what the
    model is looking at, and it also strips the clothing a dropped picture is
    meant to keep."""

    prompt = build_character_scene_prompt(
        "a rabbit having a picnic", [], dropped_appearance=""
    )

    assert "Doodle's drawing of" not in prompt
    assert "the line drawing Doodle has already made" not in prompt
    assert DROPPED_PICTURE_RULE in prompt


def test_a_cast_keeps_its_portrait_rule_when_a_picture_is_dropped() -> None:
    """Both references are in the same request and they are different kinds of
    thing, so both rules have to be present and each has to be true of its
    own picture."""

    prompt = build_character_scene_prompt(
        "at the beach",
        [("Ida", "person", "", "")],
        dropped_appearance="",
    )

    assert "the line drawing Doodle has already made" in prompt
    assert DROPPED_PICTURE_RULE in prompt


def test_a_dropped_picture_keeps_what_it_is_wearing() -> None:
    """The opposite instruction to the portrait rule's, and deliberately so. A
    saved character recurs, so their outfit is not part of who they are; a
    dropped picture is used once and the waistcoat is why it was dropped."""

    assert "Keep what it is wearing or carrying" in DROPPED_PICTURE_RULE


def test_a_dropped_picture_is_not_traced() -> None:
    """The free local threshold pass in Doodle Studio traces edges. This path
    draws the thing instead, and the model has to be told which errand it is
    on or it returns a tidied-up photograph."""

    assert "do not trace its edges" in DROPPED_PICTURE_RULE
    assert "background" in DROPPED_PICTURE_RULE


def test_a_dropped_picture_earns_the_face_exemption() -> None:
    """Doodle never inspects the picture, so it cannot know whether this is a
    child or a teddy. The two fail in opposite directions and only one of them
    is recoverable: spending the exemption on a toy costs nothing, withholding
    it from a child gives back the stock cartoon."""

    prompt = build_character_scene_prompt(
        "at the beach", [], dropped_appearance="A small girl with curly hair."
    )

    assert FACE_DETAIL_EXEMPTION in prompt
    assert GENERIC_FACE_REFUSAL in prompt


def test_one_dropped_picture_is_never_asked_to_be_told_apart() -> None:
    """TOLD_APART_RULE is about two saved people being confused with each
    other. One dropped picture has nobody to be confused with."""

    prompt = build_character_scene_prompt(
        "at the beach", [], dropped_appearance="A small girl with curly hair."
    )

    assert TOLD_APART_RULE not in prompt


def test_the_dropped_rule_is_spliced_to_the_margin() -> None:
    """A multi-line constant inserted flush left defeats dedent()'s common
    prefix calculation and every other line comes out with a literal
    four-space indent the drawing service would receive."""

    prompt = build_character_scene_prompt("at the beach", [], dropped_appearance="")

    for line in prompt.splitlines():
        assert not line.startswith("    "), f"ragged margin: {line!r}"


def test_the_dropped_rule_is_read_after_the_profile_lines() -> None:
    """The same ordering the face exemption needs: a rule stated before the
    four simplifying profile lines is overruled by them."""

    prompt = build_character_scene_prompt("at the beach", [], dropped_appearance="")

    assert prompt.index("Detail profile:") < prompt.index(FACE_DETAIL_EXEMPTION)


def test_the_foreground_rule_no_longer_says_named_characters() -> None:
    """It now covers a dropped picture too, which has no name."""

    assert "named characters" not in CAST_FOREGROUND_RULE
    prompt = build_character_scene_prompt("at the beach", [], dropped_appearance="")
    assert CAST_FOREGROUND_RULE in prompt


def test_no_rule_calls_a_dropped_picture_a_drawing_of_a_character() -> None:
    """PORTRAIT_MATCH_RULE was gated behind a cast for this reason, and two
    older rules were left saying the same thing one sentence apart. A
    drop-with-no-cast prompt used to carry the new rule saying the reference is
    a photograph alongside two asserting it is Doodle's drawing of a named
    character."""

    prompt = build_character_scene_prompt(
        "having a picnic", [], dropped_appearance="A knitted rabbit."
    )

    for lie in (
        "The attached drawing tells you",
        "the line drawing Doodle has already made",
        "how these characters really look",
        "Doodle's drawing of",
    ):
        assert lie not in prompt, f"a dropped photograph is called a drawing: {lie!r}"


def test_the_pose_rule_still_refuses_the_nodding_doll() -> None:
    """Reworded to cover a photograph as well as a portrait, so check the
    instruction it exists for survived the rewording. A photograph has the same
    problem a portrait does: one forward-facing snapshot repeated in every
    picture."""

    assert "forward-facing smile in every picture" in POSE_FREEDOM_RULE
    assert "doll rather" in POSE_FREEDOM_RULE
    prompt = build_character_scene_prompt("having a picnic", [], dropped_appearance="")
    assert POSE_FREEDOM_RULE in prompt
