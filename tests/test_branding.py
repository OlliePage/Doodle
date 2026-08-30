from pathlib import Path


def test_doodle_brand_and_minimal_homepage_are_present() -> None:
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'page_title="Doodle"' in app_source
    assert '_doodle_logo("hero")' in app_source
    assert 'placeholder="What shall we draw?"' in app_source
    assert '[data-testid="stSidebar"] {display: none !important;}' in app_source
    assert 'st.title("Colouring Factory")' not in app_source
