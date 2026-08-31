import pytest

from colouring_factory.characters import (
    characters_root,
    delete_character,
    list_characters,
    load_character,
    load_character_image,
    save_character,
)

PHOTO = b"\x89PNG\r\n\x1a\n" + b"photo bytes"
PORTRAIT = b"\x89PNG\r\n\x1a\n" + b"portrait bytes"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)


def test_a_saved_character_comes_back_whole() -> None:
    character_id = save_character(
        photo=PHOTO,
        portrait=PORTRAIT,
        name="Ida",
        kind="person",
        marks="Curly hair to her shoulders, round glasses.",
    )

    saved = load_character(character_id)
    assert saved.name == "Ida"
    assert saved.kind == "person"
    assert saved.marks == "Curly hair to her shoulders, round glasses."
    assert load_character_image(character_id) == PORTRAIT
    assert load_character_image(character_id, portrait=False) == PHOTO


def test_characters_come_back_newest_first() -> None:
    for name in ("Ida", "Bo", "Bear"):
        save_character(
            photo=PHOTO, portrait=PORTRAIT, name=name, kind="person", marks="x"
        )
    assert [c.name for c in list_characters()] == ["Bear", "Bo", "Ida"]


def test_a_nameless_character_is_refused() -> None:
    with pytest.raises(ValueError):
        save_character(
            photo=PHOTO, portrait=PORTRAIT, name="   ", kind="person", marks="x"
        )


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        save_character(
            photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="dragon", marks="x"
        )


def test_a_folder_missing_its_metadata_is_skipped_rather_than_fatal() -> None:
    save_character(photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks="x")
    (characters_root() / "half-written").mkdir()
    assert [c.name for c in list_characters()] == ["Ida"]


def test_deleting_removes_the_only_copy() -> None:
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks="x"
    )
    delete_character(character_id)
    assert list_characters() == []
    assert not (characters_root() / character_id).exists()


def test_a_traversing_id_is_refused() -> None:
    with pytest.raises(ValueError):
        delete_character("../../etc")
