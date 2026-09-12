import json

import pytest

from colouring_factory.storage import (
    attach_pair,
    clear_history_keep_favourites,
    data_root,
    delete_library_item,
    is_favourite,
    list_library_items,
    load_doodle,
    load_library_image,
    load_settings,
    record_doodle,
    save_library_item,
    save_settings,
    set_favourite,
    update_doodle,
)


def test_library_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COLOURING_FACTORY_DATA_DIR", str(tmp_path))
    item_id = save_library_item(
        processed_image=b"processed",
        raw_image=b"raw",
        title="My picture",
        metadata={"source": "test"},
    )
    items = list_library_items()
    assert len(items) == 1
    assert items[0]["id"] == item_id
    assert items[0]["title"] == "My picture"
    assert load_library_image(item_id) == b"processed"
    assert load_library_image(item_id, prefer_raw=True) == b"raw"

    delete_library_item(item_id)
    assert list_library_items() == []


def test_settings_round_trip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("COLOURING_FACTORY_DATA_DIR", str(tmp_path))
    save_settings({"calibration": {"x_scale": 1.01}})
    assert load_settings()["calibration"]["x_scale"] == 1.01


def test_doodle_data_directory_override(monkeypatch, tmp_path) -> None:
    new_root = tmp_path / "doodle-data"
    monkeypatch.setenv("DOODLE_DATA_DIR", str(new_root))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    assert data_root() == new_root
    assert new_root.exists()


def test_record_doodle_dedupes_on_raw_bytes() -> None:
    first_id = record_doodle(
        raw_image=b"same raw bytes",
        processed_image=b"processed one",
        title="First pass",
        metadata={"source": "test"},
    )
    second_id = record_doodle(
        raw_image=b"same raw bytes",
        processed_image=b"processed two",
        title="Second pass",
        metadata={"source": "test"},
    )
    assert second_id == first_id
    assert len(list_library_items()) == 1


def test_record_doodle_marks_new_entries_not_favourite() -> None:
    item_id = record_doodle(
        raw_image=b"raw",
        processed_image=b"processed",
        title="A doodle",
        metadata={},
    )
    items = list_library_items()
    assert items[0]["id"] == item_id
    assert is_favourite(items[0]) is False


def test_legacy_entry_without_favourite_key_counts_as_favourite() -> None:
    item_id = save_library_item(
        processed_image=b"processed",
        raw_image=b"raw",
        title="Old save",
        metadata={},
    )
    folder = data_root() / "library" / item_id
    metadata_file = folder / "metadata.json"
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    del payload["favourite"]
    metadata_file.write_text(json.dumps(payload), encoding="utf-8")

    items = list_library_items()
    assert is_favourite(items[0]) is True

    cleared = clear_history_keep_favourites()
    assert cleared == 0
    assert len(list_library_items()) == 1


def test_set_favourite_round_trips() -> None:
    item_id = record_doodle(
        raw_image=b"raw",
        processed_image=b"processed",
        title="A doodle",
        metadata={},
    )
    assert is_favourite(list_library_items()[0]) is False

    set_favourite(item_id, True)
    assert is_favourite(list_library_items()[0]) is True

    set_favourite(item_id, False)
    assert is_favourite(list_library_items()[0]) is False


def test_clear_history_keep_favourites_deletes_only_non_favourites() -> None:
    favourite_id = record_doodle(
        raw_image=b"raw favourite",
        processed_image=b"processed favourite",
        title="Keep me",
        metadata={},
    )
    set_favourite(favourite_id, True)
    history_id = record_doodle(
        raw_image=b"raw history",
        processed_image=b"processed history",
        title="Drop me",
        metadata={},
    )

    cleared = clear_history_keep_favourites()

    assert cleared == 1
    remaining_ids = {item["id"] for item in list_library_items()}
    assert remaining_ids == {favourite_id}
    assert history_id not in remaining_ids


def test_load_doodle_returns_pair_bytes_after_attach_pair() -> None:
    item_id = record_doodle(
        raw_image=b"raw",
        processed_image=b"processed",
        title="A doodle",
        metadata={},
    )
    assert load_doodle(item_id)["pair_raw"] is None

    attach_pair(item_id, raw_image=b"pair raw", processed_image=b"pair processed")

    loaded = load_doodle(item_id)
    assert loaded["raw"] == b"raw"
    assert loaded["processed"] == b"processed"
    assert loaded["pair_raw"] == b"pair raw"


def test_load_doodle_refuses_paths_outside_library_root() -> None:
    with pytest.raises(ValueError):
        load_doodle("../x")


def test_load_doodle_returns_none_for_missing_entry() -> None:
    assert load_doodle("does-not-exist") is None


def test_update_doodle_changes_title_and_processed_image() -> None:
    item_id = record_doodle(
        raw_image=b"raw",
        processed_image=b"processed",
        title="Original title",
        metadata={},
    )

    update_doodle(item_id, title="New title", processed_image=b"new processed")

    loaded = load_doodle(item_id)
    assert loaded["title"] == "New title"
    assert loaded["processed"] == b"new processed"
