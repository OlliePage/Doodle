"""The refine control, driven on the real Streamlit runtime.

Every button here is clicked, never merely asserted to exist. A recovery button
shipped broken past that omission on 2026-08-30.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import history
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _art(tag: str) -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=ARTWORK, prompt=tag, provider="OpenAI", model="gpt-image-2"
    )


def _studio_with_chain(chain) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["doodle_versions"] = chain
    at.session_state["current_version"] = len(chain) - 1
    at.run()
    return at


def _change_box(at: AppTest):
    for widget in at.text_input:
        if widget.label == "Make a change":
            return widget
    raise AssertionError("the refine box is missing")


def _captions(at: AppTest) -> str:
    return " ".join(caption.value for caption in at.caption)


def test_the_refine_box_appears_once_a_picture_exists() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    assert not at.exception
    assert _change_box(at) is not None


def test_the_limitation_is_stated_next_to_the_box() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    captions = _captions(at)
    assert "redrawn" in captions
    assert "costs one generation" in captions


def test_submitting_with_no_key_explains_rather_than_crashing() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    _change_box(at).set_value("give it a hat")

    submits = [b for b in at.button if b.label == "Change it"]
    assert submits, "no submit button on the refine form"
    submits[0].click().run()

    assert not at.exception
    assert any("connected" in error.value.lower() for error in at.error)


def test_submitting_an_empty_instruction_does_nothing() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    submits = [b for b in at.button if b.label == "Change it"]
    submits[0].click().run()

    assert not at.exception
    assert len(at.session_state["doodle_versions"]) == 1


def _stub_google(monkeypatch, changed: bytes):
    """Answer any Gemini call with `changed`, so no network or money is used."""

    import base64
    import json
    from io import BytesIO

    from colouring_factory import generators

    class _Reply(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self.close()
            return False

    def fake_urlopen(request, timeout=None):
        payload = {
            "steps": [
                {
                    "type": "model_output",
                    "content": [
                        {"type": "image", "data": base64.b64encode(changed).decode()}
                    ],
                }
            ]
        }
        return _Reply(json.dumps(payload).encode())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)


def _connected_studio(chain) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=180)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["doodle_versions"] = chain
    at.session_state["current_version"] = len(chain) - 1
    at.session_state["session_provider_keys"] = {"google": "AIza-fake"}
    at.run()
    return at


def test_a_successful_refinement_advances_the_chain(monkeypatch, tmp_path) -> None:
    """The happy path.

    Every other test here stops at a failure or at rendering, so all of them
    passed while three imports were missing and any real refinement raised
    NameError. Only exercising a change that succeeds catches that.
    """

    from colouring_factory.storage import load_settings, save_settings

    changed = ARTWORK + b"changed"
    at = _connected_studio(history.start(_art("original")))
    settings = load_settings()
    settings["image_provider"] = "google"
    save_settings(settings)
    _stub_google(monkeypatch, changed)
    at.run()

    _change_box(at).set_value("give the dinosaur a party hat")
    [b for b in at.button if b.label == "Change it"][0].click().run()

    assert not at.exception, [str(e.value) for e in at.exception]
    assert not at.error, [e.value for e in at.error]

    chain = at.session_state["doodle_versions"]
    assert len(chain) == 2
    assert chain[1].instruction == "give the dinosaur a party hat"
    assert chain[1].parent == 0
    assert chain[1].artwork.image_bytes == changed
    assert at.session_state["current_version"] == 1


def test_a_second_refinement_builds_on_the_first(monkeypatch, tmp_path) -> None:
    from colouring_factory.storage import load_settings, save_settings

    at = _connected_studio(history.start(_art("original")))
    settings = load_settings()
    settings["image_provider"] = "google"
    save_settings(settings)
    _stub_google(monkeypatch, ARTWORK + b"one")
    at.run()

    _change_box(at).set_value("add a hat")
    [b for b in at.button if b.label == "Change it"][0].click().run()

    _stub_google(monkeypatch, ARTWORK + b"two")
    _change_box(at).set_value("add wellington boots")
    [b for b in at.button if b.label == "Change it"][0].click().run()

    assert not at.exception
    chain = at.session_state["doodle_versions"]
    assert len(chain) == 3
    assert [v.parent for v in chain] == [None, 0, 1]


def test_a_click_while_a_change_is_already_in_flight_changes_nothing_more(
    monkeypatch, tmp_path
) -> None:
    """Streamlit can queue a click made while this control's own previous
    press is still blocked in the drawing service's call, and replay it the
    instant that call returns — a second generation from one press."""

    from colouring_factory.storage import load_settings, save_settings

    at = _connected_studio(history.start(_art("original")))
    settings = load_settings()
    settings["image_provider"] = "google"
    save_settings(settings)
    _stub_google(monkeypatch, ARTWORK + b"one")
    at.run()

    _change_box(at).set_value("add a hat")
    at.session_state["busy_refine_studio"] = True
    [b for b in at.button if b.label == "Change it"][0].click().run()

    assert not at.exception
    assert len(at.session_state["doodle_versions"]) == 1


def test_a_failed_change_leaves_the_control_pressable_again(monkeypatch) -> None:
    from colouring_factory import generators
    from colouring_factory.storage import load_settings, save_settings

    def refuse(**kwargs):
        raise generators.GeneratorError(
            "Google Gemini declined that description.",
            provider="Google Gemini",
            code="content",
        )

    monkeypatch.setattr(generators, "refine_with_provider", refuse)

    at = _connected_studio(history.start(_art("original")))
    settings = load_settings()
    settings["image_provider"] = "google"
    save_settings(settings)
    at.run()

    _change_box(at).set_value("give it a hat")
    [b for b in at.button if b.label == "Change it"][0].click().run()

    assert not at.exception
    assert at.session_state["busy_refine_studio"] is False


def test_the_version_strip_shows_the_chain_and_can_step_back() -> None:
    chain = history.start(_art("original"))
    chain = history.append(chain, _art("hatted"), "add a hat", parent=0)
    at = _studio_with_chain(chain)

    captions = _captions(at)
    assert "2 versions" in captions
    assert "add a hat" in captions

    back = [b for b in at.button if "Go back" in b.label]
    assert back, "no way to return to an earlier version"

    # Click it, do not merely assert it renders.
    back[0].click().run()
    assert not at.exception
    assert at.session_state["current_version"] == 0


def test_stepping_back_does_not_delete_later_versions() -> None:
    chain = history.start(_art("original"))
    chain = history.append(chain, _art("hatted"), "add a hat", parent=0)
    at = _studio_with_chain(chain)

    back = [b for b in at.button if "Go back" in b.label]
    back[0].click().run()

    assert len(at.session_state["doodle_versions"]) == 2


def test_a_single_version_shows_no_strip() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    assert not [b for b in at.button if "Go back" in b.label]
    assert "versions drawn" not in _captions(at)


def test_the_result_screen_carries_the_same_control() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.session_state["doodle_versions"] = history.start(_art("original"))
    at.session_state["current_version"] = 0
    at.run()

    assert not at.exception
    assert _change_box(at) is not None


def test_a_new_doodle_leaves_no_version_chain_behind() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["doodle_versions"] = history.start(_art("original"))
    at.session_state["current_version"] = 0
    at.run()

    for button in at.button:
        if button.label == "New doodle":
            button.click().run()
            break
    else:
        raise AssertionError("New doodle button not found")

    assert at.session_state["doodle_versions"] == ()
    assert at.session_state["current_version"] == 0


def test_a_demo_doodle_starts_its_own_version_chain() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["quick_mode"] = "demo"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["doodle_versions"] = history.start(_art("earlier"))
    at.run()

    chain = at.session_state["doodle_versions"]
    assert len(chain) == 1
    assert chain[0].artwork.image_bytes == at.session_state["current_raw"]


def test_the_result_screen_survives_unprepared_outputs() -> None:
    """Reaching the result screen without preparing outputs must not crash.

    _render_first_result hands quick_processed straight to sha256, so a None
    raises TypeError and the whole page dies rather than showing anything.
    """

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = None
    at.session_state["quick_pdf"] = None
    at.run()

    assert not at.exception


def test_the_wordmark_goes_home_from_every_screen_that_carries_it() -> None:
    """The logo in the corner is a route, not decoration.

    Every app with a wordmark in the top-left has taught people that pressing
    it goes home, and this one did nothing. Streamlit cannot make a markdown
    block clickable and a plain anchor cannot be clicked in a test, so a real
    button is laid over the logo — which means this test has to click it, or
    the invisible button could sit there dead and nobody would know.
    """

    for screen in ("result", "studio"):
        at = AppTest.from_file(APP, default_timeout=120)
        at.session_state["screen"] = screen
        at.session_state["current_raw"] = ARTWORK
        at.session_state["current_title"] = "A blue dinosaur"
        at.session_state["current_metadata"] = {"source": "test"}
        if screen == "result":
            at.session_state["quick_processed"] = ARTWORK
            at.session_state["quick_pdf"] = b"%PDF-1.4 test"
        at.run()

        brand = [
            button
            for button in at.button
            if button.label == "Doodle, back to the homepage"
        ]
        assert brand, f"no wordmark button on the {screen} screen"

        brand[0].click().run()

        assert not at.exception
        assert at.session_state["screen"] == "home", (
            f"the wordmark did not go home from the {screen} screen"
        )
        assert at.session_state["current_raw"] is None
