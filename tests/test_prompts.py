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
