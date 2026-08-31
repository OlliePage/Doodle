from types import SimpleNamespace

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


@pytest.fixture
def guard(tmp_path):
    """Plants real targets around (and inside) the store, so every traversal
    shape below can be proved harmless rather than merely refused."""
    root = characters_root()

    sentinel = tmp_path / "sentinel" / "precious.txt"
    sentinel.parent.mkdir()
    sentinel.write_bytes(b"do not delete me")

    # A directory that merely starts with the store's own name, sitting right
    # alongside it. This is the shape a naive containment check gets wrong: a
    # plain `str(folder).startswith(str(root))` treats "characters-evil" as
    # inside "characters" because one string happens to prefix the other.
    sibling_dir = root.parent / f"{root.name}-evil"
    sibling_dir.mkdir(parents=True)
    sibling_secret = sibling_dir / "secret.txt"
    sibling_secret.write_bytes(b"keep me too")

    # A symlink living inside the store but pointing straight out of it.
    # Containment has to be checked on the resolved target, not the raw join.
    (root / "evil_link").symlink_to(sentinel.parent)

    shapes = {
        "parent-climb": "../../etc",
        "bare-dotdot": "..",
        "bare-dotdot-slash": "../",
        "deep-climb": "../../../../../../etc/passwd",
        "absolute-system-path": "/etc/passwd",
        "absolute-path-to-sentinel": str(sentinel),
        "sibling-prefix-directory": f"../{root.name}-evil",
        "empty-id": "",
        "null-byte": "evil\x00../../etc",
        "symlink-escape": "evil_link",
    }
    return SimpleNamespace(
        shapes=shapes,
        sentinel=sentinel,
        sentinel_bytes=sentinel.read_bytes(),
        sibling_secret=sibling_secret,
        sibling_bytes=sibling_secret.read_bytes(),
    )


@pytest.mark.parametrize(
    "shape_name",
    [
        "parent-climb",
        "bare-dotdot",
        "bare-dotdot-slash",
        "deep-climb",
        "absolute-system-path",
        "absolute-path-to-sentinel",
        "sibling-prefix-directory",
        "empty-id",
        "null-byte",
        "symlink-escape",
    ],
)
def test_a_traversing_id_is_refused(guard, shape_name) -> None:
    with pytest.raises(ValueError):
        delete_character(guard.shapes[shape_name])
    # The proof that matters isn't only "an exception happened" — it's that
    # nothing outside the store was ever touched.
    assert guard.sentinel.exists()
    assert guard.sentinel.read_bytes() == guard.sentinel_bytes
    assert guard.sibling_secret.exists()
    assert guard.sibling_secret.read_bytes() == guard.sibling_bytes


def test_a_look_alike_traversal_is_contained_not_touching_anything(guard) -> None:
    # Four literal dots is a valid, if odd, folder name, not a "../" climb, so
    # this resolves to a path that is still inside the store — a nested folder
    # that doesn't exist — and delete_character's existence check makes it a
    # silent no-op rather than a bypass. Recorded here so the next reader does
    # not mistake "no error raised" for "no guard".
    delete_character("....//....//etc")
    assert guard.sentinel.exists()
    assert guard.sentinel.read_bytes() == guard.sentinel_bytes
    assert guard.sibling_secret.exists()
    assert guard.sibling_secret.read_bytes() == guard.sibling_bytes
