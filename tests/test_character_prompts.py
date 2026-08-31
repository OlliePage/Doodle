import pytest

from colouring_factory.prompts import (
    BADGE_CORNERS_RULE,
    FACE_DETAIL_EXEMPTION,
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


def test_a_scene_with_no_characters_is_refused() -> None:
    with pytest.raises(ValueError):
        build_character_scene_prompt("walking in a forest", [])
