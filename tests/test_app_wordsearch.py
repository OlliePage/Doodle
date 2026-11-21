"""Word searches, driven through the real Streamlit runtime.

Every control a parent touches is clicked and its effect asserted, with the
drawing service and the text model faked so nothing is paid for.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, wordsearch_words
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import list_library_items, load_settings, save_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
PICTURE = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def drawn(monkeypatch) -> list[str]:
    """Every clue picture requested, by prompt; the service is a stand-in."""

    prompts: list[str] = []

    def fake(**kwargs):
        prompts.append(kwargs["prompts"][0])
        return [GeneratedArtwork(PICTURE, kwargs["prompts"][0], "openai", "m")]

    monkeypatch.setattr(generators, "generate_with_provider", fake)
    return prompts


def _word_search_home(difficulty: str = "4-5 years") -> AppTest:
    settings = load_settings()
    settings["home_mode"] = "Word search"
    settings["wordsearch_difficulty"] = difficulty
    save_settings(settings)
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    return at


def _make(at: AppTest, text: str) -> AppTest:
    at.text_input(key="home_prompt").set_value(text).run()
    button = next(b for b in at.button if b.label == "Make the word search")
    button.click().run()
    return at


def test_switching_mode_changes_the_button_and_hides_the_drawing_items() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert any(b.label == "Draw it" for b in at.button)
    assert "How many to draw" in [s.label for s in at.segmented_control]

    at.segmented_control(key="home_mode").set_value("Word search").run()
    assert not at.exception
    labels = [b.label for b in at.button]
    assert "Make the word search" in labels
    assert "Draw it" not in labels
    assert "A topic, or your own words: cat, dog, hen" == (
        at.text_input(key="home_prompt").placeholder
    )
    # The drawing items are gone, the difficulty is there, and the model stays.
    assert "How many to draw" not in [s.label for s in at.segmented_control]
    assert "Drawing style" not in [str(c.value) for c in at.caption]
    assert at.radio(key="ws_difficulty_pick")
    assert at.selectbox(key="home_model_openai")
    assert load_settings()["home_mode"] == "Word search"

    at.segmented_control(key="home_mode").set_value("Colouring page").run()
    assert any(b.label == "Draw it" for b in at.button)
    assert load_settings()["home_mode"] == "Colouring page"


def test_typed_words_make_a_sheet_with_a_preview_and_a_pdf(drawn) -> None:
    at = _make(_word_search_home(), "cat, dog, hen")

    assert not at.exception
    assert at.session_state["screen"] == "wordsearch_result"
    sheet = at.session_state["ws_sheet"]
    assert sheet["pdf"].startswith(b"%PDF")
    assert sheet["preview"].startswith(b"\x89PNG")
    assert [d for d, _letters in sheet["words"]] == ["cat", "dog", "hen"]
    assert len(at.image) >= 1
    assert any(b.label == "Print this word search" for b in at.button)
    assert len(at.get("download_button")) >= 1
    assert len(drawn) == 3
    # Pressing the primary button must not crash the page.
    at.button(key="print_wordsearch").click().run()
    assert not at.exception


def test_a_topic_is_turned_into_words_by_the_text_model(monkeypatch, drawn) -> None:
    asked: list[str] = []

    def fake_text(model, api_key, instruction):
        asked.append(instruction)
        return '["cat", "dog", "hen", "cow", "pig", "fox"]'

    monkeypatch.setattr(wordsearch_words, "_openai_text", fake_text)
    at = _make(_word_search_home(), "farm animals")

    assert not at.exception
    assert at.session_state["screen"] == "wordsearch_result"
    sheet = at.session_state["ws_sheet"]
    assert sheet["title"] == "Farm animals"
    assert len(asked) == 1 and "farm animals" in asked[0]
    # 4-5 years takes five words, so the sixth the model offered is dropped.
    assert [d for d, _l in sheet["words"]] == ["cat", "dog", "hen", "cow", "pig"]


def test_a_topic_nobody_has_words_for_is_explained_on_the_homepage(
    monkeypatch, drawn
) -> None:
    def broken(model, api_key, instruction):
        raise RuntimeError("offline")

    monkeypatch.setattr(wordsearch_words, "_openai_text", broken)
    at = _make(_word_search_home(), "zzqxv")

    assert at.session_state["screen"] == "home"
    assert at.session_state["home_error_code"] == "unknown_topic"
    assert any("no words" in str(e.value).lower() for e in at.error)
    assert drawn == []


def test_switching_pictures_off_draws_nothing(drawn) -> None:
    at = _word_search_home()
    at.toggle(key="ws_pictures").set_value(False).run()
    assert load_settings()["wordsearch_pictures"] is False

    at = _make(at, "cat, dog, hen")

    assert at.session_state["screen"] == "wordsearch_result"
    assert drawn == []
    assert at.session_state["ws_sheet"]["pictures"] is False


def test_a_custom_difficulty_can_be_saved_and_chosen_again(drawn) -> None:
    at = _word_search_home()
    at.slider(key="ws_custom_size").set_value(7).run()
    assert load_settings()["wordsearch_difficulty"] == "custom"

    at.text_input(key="ws_fav_name").set_value("Zara").run()
    at.button(key="ws_fav_save").click().run()
    settings = load_settings()
    assert [f["name"] for f in settings["wordsearch_favourites"]] == ["Zara"]
    assert settings["wordsearch_favourites"][0]["settings"]["rows"] == 7
    assert settings["wordsearch_difficulty"] == "fav:Zara"

    at.radio(key="ws_difficulty_pick").set_value("2-3 years").run()
    assert load_settings()["wordsearch_difficulty"] == "2-3 years"
    at.radio(key="ws_difficulty_pick").set_value("fav:Zara").run()
    assert load_settings()["wordsearch_difficulty"] == "fav:Zara"

    at = _make(at, "cat, dog, hen")
    assert at.session_state["screen"] == "wordsearch_result"
    assert at.session_state["ws_sheet"]["settings"]["rows"] == 7
    assert len(at.session_state["ws_sheet"]["puzzle"].grid) == 7


def test_a_saved_favourite_can_be_deleted() -> None:
    at = _word_search_home()
    at.text_input(key="ws_fav_name").set_value("Zara").run()
    at.button(key="ws_fav_save").click().run()
    assert load_settings()["wordsearch_difficulty"] == "fav:Zara"

    at.button(key="ws_fav_delete_Zara").click().run()

    settings = load_settings()
    assert settings["wordsearch_favourites"] == []
    assert settings["wordsearch_difficulty"] in {"2-3 years", "4-5 years"}
    assert "fav:Zara" not in at.radio(key="ws_difficulty_pick").options


def test_make_another_gives_a_new_grid_from_the_same_words(drawn) -> None:
    at = _make(_word_search_home(), "cat, dog, hen")
    before = at.session_state["ws_sheet"]
    requests = len(drawn)

    at.button(key="ws_make_another").click().run()

    assert not at.exception
    after = at.session_state["ws_sheet"]
    assert after["words"] == before["words"]
    assert after["puzzle"].grid != before["puzzle"].grid
    assert after["seed"] != before["seed"]
    assert len(drawn) == requests
    assert at.session_state["screen"] == "wordsearch_result"


def test_the_sheet_is_in_history_and_reopens_as_a_word_search(drawn) -> None:
    at = _make(_word_search_home(), "cat, dog, hen")
    sheet = at.session_state["ws_sheet"]
    (item,) = list_library_items()
    assert item["metadata"]["kind"] == "wordsearch"
    assert item["metadata"]["words"] == [list(w) for w in sheet["words"]]

    at.button(key="top_new_wordsearch").click().run()
    assert at.session_state["screen"] == "home"
    assert at.session_state["ws_sheet"] is None

    at.button(key="home_history_link").click().run()
    assert at.session_state["screen"] == "history"
    at.button(key=f"history_open_{item['id']}").click().run()

    assert not at.exception
    assert at.session_state["screen"] == "wordsearch_result"
    reopened = at.session_state["ws_sheet"]
    assert reopened["puzzle"].grid == sheet["puzzle"].grid
    assert reopened["pdf"].startswith(b"%PDF")
    assert len(drawn) == 3  # the pictures came back from the cache


def test_a_typed_word_too_long_for_the_grid_offers_one_that_holds_it(drawn) -> None:
    # Typed words were chosen on purpose, so none is quietly dropped: the
    # sheet waits, and the smallest grid that holds ELEPHANT is offered.
    at = _make(_word_search_home(), "cat, dog, elephant")

    assert at.session_state["screen"] == "home"
    assert drawn == []
    assert "An 8 × 8 grid holds every one" in " ".join(str(e.value) for e in at.error)
    assert at.button(key="ws_fit_grow").label == "Make it on an 8 × 8 grid"


def test_typed_words_are_kept_even_past_the_presets_word_count(drawn) -> None:
    # A parent's own words are chosen on purpose; the preset's word count is
    # for picking from a topic, so seven typed words make seven, not three.
    at = _make(_word_search_home(), "cat, dog, hen, cow, pig, owl, ant")

    assert len(at.session_state["ws_sheet"]["puzzle"].placed) == 7


def test_the_longest_word_setting_is_saved_with_a_custom_difficulty() -> None:
    at = _word_search_home()
    at.slider(key="ws_custom_size").set_value(10).run()
    at.slider(key="ws_custom_maxlen").set_value(7).run()

    assert not at.exception
    settings = load_settings()
    assert settings["wordsearch_difficulty"] == "custom"
    assert settings["wordsearch_custom"]["max_len"] == 7


def test_too_many_words_for_the_grid_says_so_and_offers_a_bigger_one(drawn) -> None:
    words = "cat, dog, hen, cow, pig, owl, ant, bee, elk, yak, emu, fox, rat"
    at = _make(_word_search_home(), words)

    # Nothing is drawn or paid for until the words fit.
    assert at.session_state["screen"] == "home"
    assert drawn == []
    errors = " ".join(str(e.value) for e in at.error)
    assert "13 words will not all fit on a 6 × 6 grid" in errors

    grow = at.button(key="ws_fit_grow")
    assert grow.label.startswith("Make it on a ")
    at = grow.click().run()

    assert not at.exception
    assert at.session_state["screen"] == "wordsearch_result"
    sheet = at.session_state["ws_sheet"]
    assert len(sheet["puzzle"].placed) == 13
    assert sheet["puzzle"].skipped == ()
    assert load_settings()["wordsearch_difficulty"] == "custom"


def test_a_list_too_big_for_any_grid_is_refused_plainly(drawn) -> None:
    words = ", ".join(f"word{chr(97 + i % 26)}{chr(97 + i // 26)}x" for i in range(100))
    at = _make(_word_search_home(), words)

    assert at.session_state["screen"] == "home"
    assert drawn == []
    assert "biggest grid, 15 × 15" in " ".join(str(e.value) for e in at.error)


def test_the_longest_word_never_exceeds_the_grid_width() -> None:
    at = _word_search_home()
    at.slider(key="ws_custom_size").set_value(5).run()
    at.slider(key="ws_custom_maxlen").set_value(9).run()

    assert load_settings()["wordsearch_custom"]["max_len"] == 5
