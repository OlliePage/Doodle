import pytest

from colouring_factory.prompts import (
    BADGE_CORNERS_RULE,
    FACE_DETAIL_EXEMPTION,
    NAMED_CHARACTER_RULE,
    TOY_LIKENESS_RULE,
    build_caricature_prompt,
    build_character_scene_prompt,
)


def test_each_character_is_named_and_matched_to_its_picture() -> None:
    prompt = build_character_scene_prompt(
        "building a sandcastle",
        [
            ("Ida", "person", "Curly hair, round glasses."),
            ("Bear", "toy", "A bald patch on one ear."),
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
            ("Ida", "person", "Curly hair, round glasses."),
            ("Bear", "toy", "A bald patch on one ear."),
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
        "walking in a forest", [("Ida", "person", "Curly hair.")]
    )
    toy_only = build_character_scene_prompt(
        "having a picnic", [("Bear", "toy", "A bald patch on one ear.")]
    )

    assert FACE_DETAIL_EXEMPTION in with_person
    assert FACE_DETAIL_EXEMPTION not in toy_only


def test_hair_is_drawn_as_closed_shapes_not_strands() -> None:
    """Strands a pixel wide lose about a fifth of their ink to the despeckle
    pass and come back broken, so the rule is in the prompt rather than hoped
    for."""

    prompt = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.")]
    )
    assert "never as separate strands" in prompt


def test_the_colouring_book_contract_survives() -> None:
    prompt = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.")]
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

    toy = build_character_scene_prompt("a picnic", [("Bear", "toy", "A bald ear.")])
    character = build_character_scene_prompt(
        "a picnic", [("Bear", "character", "A bald ear.")]
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
            ("Ida", "person", "Curly hair, round glasses."),
            ("Bear", "toy", "A bald patch on one ear."),
        ],
    )
    caricature = build_caricature_prompt("Ida", "person", "Curly hair, round glasses.")

    for prompt in (scene, caricature):
        for line in prompt.splitlines():
            assert not line[:1].isspace(), f"ragged line: {line!r}"
