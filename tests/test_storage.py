from colouring_factory.storage import (
    data_root,
    delete_library_item,
    list_library_items,
    load_library_image,
    load_settings,
    save_library_item,
    save_settings,
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
