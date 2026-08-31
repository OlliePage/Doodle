import pytest

from colouring_factory.prompts import (
    BADGE_CORNERS_RULE,
    CAST_FOREGROUND_RULE,
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

    assert "The first picture is Ida" in prompt
    assert "The second picture is Bear" in prompt


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
    assert "never as many fine separate strands" in prompt


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
