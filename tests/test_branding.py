from pathlib import Path


def test_homepage_is_branded_and_minimal() -> None:
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    assert 'page_title="Doodle"' in app_source
    assert "doodle-logo--hero" in app_source
    assert 'placeholder="What shall we draw?"' in app_source
    assert '[data-testid="stSidebar"] {display: none !important;}' in app_source
    assert 'st.title("Colouring Factory")' not in app_source


def test_the_prompt_bar_hint_lives_outside_the_input() -> None:
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )

    # Streamlit's own hint and clear button are right-aligned inside the input
    # and collide with each other and the pill's rounded edge, so both are
    # hidden and replaced with a Draw it button below the bar.
    assert '[data-testid="InputInstructions"]' in app_source
    assert '"Draw it"' in app_source
    assert "stFormSubmitButton" in app_source
