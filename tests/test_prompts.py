from colouring_factory.prompts import build_colouring_prompt


def test_prompt_contains_concept_and_print_rules() -> None:
    prompt = build_colouring_prompt(
        "A small dragon baking a cake",
        age_profile="2-3 years",
        style_name="Toddler bold",
        target="Round badge",
    )
    assert "A small dragon baking a cake" in prompt
    assert "Black line work only" in prompt
    assert "No border, words" in prompt
    assert "circular crop" in prompt
    assert "existing television" in prompt


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
