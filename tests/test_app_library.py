"""History, favourites and getting back to a doodle, driven on the real
Streamlit runtime.

Every doodle is now recorded automatically the moment it is the picture on
screen, and a saved doodle used to be the only kind that came back at all.
Every route added or changed to make history and favourites real is clicked
here, not merely asserted to render.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import generators, variations
from colouring_factory.models import GeneratedArtwork
from colouring_factory.storage import (
    attach_pair,
    data_root,
    is_favourite_id,
    list_library_items,
    load_doodle,
    record_doodle,
    save_library_item,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()
OTHER = (PROJECT_ROOT / "assets" / "demo_robot_balloons.png").read_bytes()
PAIR = (PROJECT_ROOT / "assets" / "style_a_scene.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _seed(title: str = "Blue dinosaur") -> str:
    return save_library_item(
        processed_image=ARTWORK,
        raw_image=ARTWORK,
        title=title,
        metadata={"source": "test"},
    )


def _button(at: AppTest, fragment: str):
    for button in at.button:
        if fragment.lower() in button.label.lower():
            return button
    raise AssertionError(
        f"no button matching {fragment!r}; saw {[b.label for b in at.button]}"
    )


def _has_button(at: AppTest, fragment: str) -> bool:
    return any(fragment.lower() in button.label.lower() for button in at.button)


def _text(at: AppTest) -> str:
    parts = [element.value for element in at.caption]
    parts += [element.value for element in at.markdown]
    parts += [element.value for element in at.success]
    parts += [element.value for element in at.info]
    parts += [element.value for element in at.warning]
    return " ".join(str(part) for part in parts)


def _result_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()
    return at


def _fake_generate(**kwargs):
    prompt = kwargs["prompts"][0]
    match = re.search(r"reading (\d+) of", prompt)
    index = int(match.group(1)) - 1 if match else 0
    images = [ARTWORK, OTHER]
    return [
        GeneratedArtwork(
            image_bytes=images[index % len(images)],
            prompt=prompt,
            provider="OpenAI",
            model="gpt-image-2",
        )
    ]


def _fake_briefs(idea, count, **kwargs):
    return [f"reading {index + 1} of {idea}" for index in range(count)]


def test_a_drawn_picture_appears_in_history_without_pressing_anything(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(generators, "generate_with_provider", _fake_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at.text_input(key="home_prompt").set_value("a blue dinosaur")
    at = _button(at, "draw it").click().run()

    assert not at.exception
    assert at.session_state["screen"] == "result"
    items = list_library_items()
    assert len(items) == 1
    assert items[0]["title"] == "a blue dinosaur"


def test_tapping_an_alternative_adds_it_and_tapping_back_does_not_duplicate(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setattr(generators, "generate_with_provider", _fake_generate)
    monkeypatch.setattr(variations, "build_variation_briefs", _fake_briefs)

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    at = at.segmented_control(key="home_alternatives").set_value(2).run()
    at.text_input(key="home_prompt").set_value("a dinosaur washing a fire engine")
    at = _button(at, "draw it").click().run()

    # Only the alternative actually shown is recorded; the other was drawn
    # but never adopted.
    assert len(list_library_items()) == 1

    at = _button(at, "use this one").click().run()
    assert len(list_library_items()) == 2

    # Tapping back to the first reuses its entry rather than writing a
    # second copy of the same raw bytes.
    at = _button(at, "use this one").click().run()
    assert len(list_library_items()) == 2


def test_the_heart_adds_and_removes_a_favourite_and_the_label_flips() -> None:
    at = _result_screen()
    assert _has_button(at, "add to favourites")

    at = _button(at, "add to favourites").click().run()
    assert not at.exception
    doodle_id = at.session_state["current_doodle_id"]
    assert is_favourite_id(doodle_id)
    assert _has_button(at, "remove from favourites")
    assert not _has_button(at, "add to favourites")

    at = _button(at, "remove from favourites").click().run()
    assert not at.exception
    assert not is_favourite_id(doodle_id)
    assert _has_button(at, "add to favourites")


def test_a_legacy_entry_without_the_favourite_key_shows_under_favourites() -> None:
    item_id = _seed("Old save")
    metadata_file = data_root() / "library" / item_id / "metadata.json"
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    del payload["favourite"]
    metadata_file.write_text(json.dumps(payload), encoding="utf-8")

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "favourites"
    at.run()
    assert not at.exception
    assert "Old save" in _text(at)


def test_opening_from_history_lands_on_the_result_screen_ready_to_print() -> None:
    item_id = record_doodle(
        raw_image=ARTWORK,
        processed_image=ARTWORK,
        title="Blue dinosaur",
        metadata={"concept": "a blue dinosaur", "source": "test"},
    )
    attach_pair(item_id, raw_image=OTHER, processed_image=OTHER)

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "history"
    at.run()

    at = _button(at, "open").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "result"
    assert at.session_state["current_raw"] == ARTWORK
    assert at.session_state["quick_processed"]
    assert at.session_state["quick_pdf"]
    assert at.session_state["generation_idea"] == "a blue dinosaur"
    assert at.session_state["pair_processed"]
    assert at.session_state["pair_pdf"]


def test_opening_a_doodle_without_a_pair_leaves_no_stale_pair_behind() -> None:
    _seed()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "history"
    at.session_state["pair_processed"] = ARTWORK
    at.session_state["pair_pdf"] = b"%PDF-1.4 stale"
    at.run()

    at = _button(at, "open").click().run()
    assert not at.exception
    assert not at.session_state["pair_processed"]
    assert not at.session_state["pair_pdf"]


def test_deleting_asks_first_and_keep_it_keeps_it() -> None:
    _seed()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "history"
    at.run()

    at = _button(at, "delete").click().run()
    assert not at.exception
    assert len(list_library_items()) == 1
    assert "cannot be undone" in _text(at)
    # _seed saves through save_library_item, which marks an entry a
    # favourite, so the confirmation must say so.
    assert "one of your favourites" in _text(at)

    at = _button(at, "keep it").click().run()
    assert not at.exception
    assert len(list_library_items()) == 1

    at = _button(at, "delete").click().run()
    at = _button(at, "delete for good").click().run()
    assert not at.exception
    assert list_library_items() == []
    assert "nothing here yet" in _text(at).lower()


def test_clear_history_keeps_favourites_and_removes_the_rest() -> None:
    favourite_id = _seed("Keep me")
    history_id = record_doodle(
        raw_image=OTHER,
        processed_image=OTHER,
        title="Drop me",
        metadata={"source": "test"},
    )

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "history"
    at.run()

    at = _button(at, "clear history, keep favourites").click().run()
    assert not at.exception
    assert "cannot be undone" in _text(at)
    # Neither entry is gone while the confirmation is still open.
    assert len(list_library_items()) == 2

    at = _button(at, "clear history").click().run()
    assert not at.exception
    remaining_ids = {item["id"] for item in list_library_items()}
    assert remaining_ids == {favourite_id}
    assert history_id not in remaining_ids


def test_studios_add_to_favourites_favourites_the_entry_under_its_new_name() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.run()

    for widget in at.text_input:
        if widget.label == "Name for this doodle":
            at = widget.set_value("Renamed dinosaur").run()
            break
    else:
        raise AssertionError("the name box is missing")

    at = _button(at, "add to favourites").click().run()
    assert not at.exception
    assert "added to your favourites" in _text(at).lower()

    doodle_id = at.session_state["current_doodle_id"]
    assert doodle_id
    favourites = {item["id"]: item for item in list_library_items(favourites_only=True)}
    assert favourites[doodle_id]["title"] == "Renamed dinosaur"


def test_the_studio_favourites_tab_shows_the_same_favourites() -> None:
    _seed()
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.run()
    assert not at.exception
    assert "Blue dinosaur" in _text(at)


def test_the_homepage_shows_neither_route_until_something_exists() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    assert not _has_button(at, "history")
    assert not _has_button(at, "favourites")

    _seed()

    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    assert _has_button(at, "history")
    assert _has_button(at, "favourites")


def test_deleting_the_doodle_on_screen_stays_deleted() -> None:
    """Deleting the doodle that is on screen used to leave it in memory, where
    the result screen recorded it again the next time it was shown: Back after
    Delete for good brought the picture straight back into History. And the
    stop that could no longer be shown was replaced by a new one, which threw
    away the way forward."""

    at = _result_screen()
    assert at.session_state["current_doodle_id"]

    at = _button(at, "history").click().run()
    at = _button(at, "delete").click().run()
    at = _button(at, "delete for good").click().run()
    assert list_library_items() == []
    assert at.session_state["current_raw"] is None

    at = next(b for b in at.button if b.label == "Back").click().run()
    assert not at.exception
    assert at.session_state["screen"] == "home"
    assert list_library_items() == []

    forward = next(b for b in at.button if b.label == "Forward")
    assert not forward.disabled
    at = forward.click().run()
    assert at.session_state["screen"] == "history"


def test_tapping_an_alternative_keeps_the_grown_up_sheet_with_it() -> None:
    """The grown-up sheet stays on screen beside whichever alternative is
    tapped, so that alternative's History entry has to keep it too; reopening
    it used to bring back the children's sheet alone."""

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Blue dinosaur"
    at.session_state["current_metadata"] = {
        "source": "test",
        "concept": "Blue dinosaur",
    }
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 fake"
    at.session_state["candidates"] = [
        GeneratedArtwork(image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="m"),
        GeneratedArtwork(image_bytes=OTHER, prompt="p", provider="OpenAI", model="m"),
    ]
    at.session_state["pair_raw"] = PAIR
    at.run()

    at = _button(at, "use this one").click().run()
    assert not at.exception
    loaded = load_doodle(at.session_state["current_doodle_id"])
    assert loaded["raw"] == OTHER
    assert loaded["pair_raw"] == PAIR
