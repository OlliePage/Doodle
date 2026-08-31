import pytest

from colouring_factory.prompts import (
    DEFAULT_STYLE,
    STYLE_PRESETS,
    build_colour_suggestion_prompt,
    build_colouring_prompt,
    build_refinement_prompt,
)


def test_a_refinement_keeps_the_colouring_book_rules() -> None:
    prompt = build_refinement_prompt("give the bear a party hat")
    assert "give the bear a party hat" in prompt
    assert "Black line work only" in prompt
    assert "Pure white background" in prompt


def test_a_refinement_asks_for_everything_else_to_stay() -> None:
    prompt = build_refinement_prompt("give the bear a party hat").lower()
    assert "unchanged" in prompt or "leave everything else" in prompt


def test_a_refinement_carries_the_style_and_age_profile() -> None:
    toddler = build_refinement_prompt("add a hat", age_profile="2-3 years")
    preschool = build_refinement_prompt("add a hat", age_profile="4-5 years")
    assert toddler != preschool


def test_a_refinement_with_an_empty_instruction_is_refused() -> None:
    with pytest.raises(ValueError):
        build_refinement_prompt("   ")


def test_prompt_contains_concept_and_print_rules() -> None:
    prompt = build_colouring_prompt(
        "A small dragon baking a cake",
        age_profile="2-3 years",
        style_name="Just the things",
        target="Round badge",
    )
    assert "A small dragon baking a cake" in prompt
    assert "Black line work only" in prompt
    assert "No border, words" in prompt
    assert "circular crop" in prompt


def test_a_variation_brief_replaces_the_bare_concept() -> None:
    brief = "The bear sits in long grass, the kite tangled in a small tree."
    prompt = build_colouring_prompt("a bear flying a kite", variation_brief=brief)
    assert brief in prompt


def test_style_and_age_rules_are_identical_across_briefs() -> None:
    first = build_colouring_prompt("a bear", variation_brief="Brief one.")
    second = build_colouring_prompt("a bear", variation_brief="Brief two.")
    assert first.replace("Brief one.", "X") == second.replace("Brief two.", "X")


def test_no_brief_leaves_the_prompt_unchanged() -> None:
    assert build_colouring_prompt("a bear") == build_colouring_prompt(
        "a bear", variation_brief=""
    )


def test_the_round_badge_rule_asks_for_a_circular_composition() -> None:
    prompt = build_colouring_prompt("a bear", target="Round badge")
    lowered = prompt.lower()
    assert "circle" in lowered or "circular" in lowered
    assert "corner" in lowered


def test_no_composed_line_is_left_ragged() -> None:
    """A multi-line rule constant spliced in flush left defeats dedent()'s
    common-prefix calculation, so the rest of the prompt keeps a literal
    four-space indent it should have lost. Caught in review on 2026-08-31 by
    diffing composed prompts before and after VISUAL_RULES was introduced."""

    for prompt in (
        build_colouring_prompt("a bear", target="Round badge"),
        build_refinement_prompt("give the bear a party hat"),
        build_colour_suggestion_prompt(
            [("Ida", "Brown eyes, dark hair, light-brown skin.")]
        ),
    ):
        for line in prompt.splitlines():
            assert not line[:1].isspace(), f"ragged line: {line!r}"


def test_a_picture_with_no_characters_colours_exactly_as_before() -> None:
    """The regression this feature must not cause: a plain idea with nobody
    in it — the sky, the grass, the sand — must colour exactly the way it
    always has."""

    assert build_colour_suggestion_prompt() == build_colour_suggestion_prompt([])
    prompt = build_colour_suggestion_prompt()
    assert "sky and water blue" in prompt
    assert "grass and leaves" in prompt
    # Nothing character-specific has leaked in when there is no cast.
    assert "real colouring" not in prompt.lower()


def test_a_characters_recorded_appearance_is_used_to_colour_them() -> None:
    prompt = build_colour_suggestion_prompt(
        [("Ida", "Brown eyes, wavy dark-brown hair, light-brown skin.")]
    )
    assert "Ida" in prompt
    assert "Brown eyes, wavy dark-brown hair, light-brown skin." in prompt


def test_getting_a_real_persons_colouring_wrong_is_named_as_a_real_mistake() -> None:
    """The forceful register the rest of this file's hard-won rules use —
    BADGE_CORNERS_RULE said "Draw NOTHING", the caricature prompt said a
    flattering portrait was "the wrong answer" — because a polite version
    of each was tried first and ignored."""

    prompt = build_colour_suggestion_prompt(
        [("Ida", "Brown eyes, dark hair, light-brown skin.")]
    )
    assert "not a small mistake" in prompt.lower() or "not a minor" in prompt.lower()
    assert "generic" in prompt.lower() or "stereotypical" in prompt.lower()


def test_more_than_one_character_are_each_named_with_their_own_colouring() -> None:
    prompt = build_colour_suggestion_prompt(
        [
            ("Ida", "Brown eyes, dark hair, light-brown skin."),
            ("Bear", "A red ribbon, worn patches on both ears."),
        ]
    )
    assert "Ida" in prompt and "Brown eyes, dark hair, light-brown skin." in prompt
    assert "Bear" in prompt and "A red ribbon, worn patches on both ears." in prompt


def test_a_character_with_no_recorded_appearance_still_gets_a_safeguard() -> None:
    """A character saved before this feature existed, or never filled in,
    carries no description at all — the model must still be told not to
    reach for a default rather than simply saying nothing about them."""

    prompt = build_colour_suggestion_prompt([("Ida", "")])
    lowered = prompt.lower()
    assert "ida" in lowered
    assert "blonde" in lowered or "fair skin" in lowered or "default" in lowered


def test_every_offered_style_is_one_the_prompt_builder_knows() -> None:
    """The homepage's list of styles used to be typed out by hand beside the
    dict the builders read, with nothing keeping the two in step. A name in one
    and not the other offers a style that is silently ignored in favour of the
    fallback, and no test noticed when four styles became two."""

    from colouring_factory.storage import QUICK_STYLE_CHOICES

    assert tuple(STYLE_PRESETS) == QUICK_STYLE_CHOICES
    assert QUICK_STYLE_CHOICES[0] == DEFAULT_STYLE, (
        "the first entry is both the default and what an unrecognised saved "
        "style is quietly rewritten to, so it must be the one that adds nothing"
    )


def test_the_default_style_adds_no_instruction_of_its_own() -> None:
    """The age setting already carries region count, line weight and texture at
    every rung. A default style that restated any of it could contradict it."""

    assert STYLE_PRESETS[DEFAULT_STYLE].instruction == ""
    prompt = build_colouring_prompt("a fox in a wood", age_profile="Grown-up")
    assert "Style profile" not in prompt, "an empty style still sent a labelled blank"


def test_a_grown_up_scene_spends_its_detail_on_the_subject() -> None:
    """Reported 2026-08-31: a grown-up portrait came back with a plainly drawn
    subject and a flowy ornamental background. The old wording offered "a
    decorative border of repeating motifs" and "patterned fills wherever a
    plain area would otherwise sit" as ways to reach 150 regions, which a model
    reads as permission to leave the subject alone."""

    prompt = build_colouring_prompt("a fox in a wood", age_profile="Grown-up")

    assert "Spend that detail on the subject first" in prompt
    assert "compensating for a plain one" in prompt
    assert "patterned fills wherever a plain area would otherwise sit" not in prompt
