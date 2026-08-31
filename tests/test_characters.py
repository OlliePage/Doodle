import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from colouring_factory.characters import (
    characters_root,
    delete_character,
    list_characters,
    load_character,
    load_character_image,
    load_character_portrait,
    save_character,
    update_character,
    update_character_portrait,
)

PHOTO = b"\x89PNG\r\n\x1a\n" + b"photo bytes"
PORTRAIT = b"\x89PNG\r\n\x1a\n" + b"portrait bytes"


def _real_png(colour=(180, 90, 40)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), colour).save(buffer, format="PNG")
    return buffer.getvalue()


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
        appearance="Brown eyes, dark wavy hair, light-brown skin.",
    )

    saved = load_character(character_id)
    assert saved.name == "Ida"
    assert saved.kind == "person"
    assert saved.marks == "Curly hair to her shoulders, round glasses."
    assert saved.appearance == "Brown eyes, dark wavy hair, light-brown skin."
    assert load_character_image(character_id) == PORTRAIT
    assert load_character_image(character_id, portrait=False) == PHOTO


def test_appearance_defaults_to_blank_when_not_given() -> None:
    # A character saved before this feature existed, or through any caller
    # that has not been taught about it, must still load rather than raise.
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks=""
    )
    assert load_character(character_id).appearance == ""


def test_a_character_json_written_before_appearance_existed_reads_as_blank() -> None:
    # A record from before this field existed has no "appearance" key at
    # all, not merely a blank one — written here exactly that way, rather
    # than through save_character, which now always writes the key.
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks="x"
    )
    path = characters_root() / character_id / "character.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["appearance"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert load_character(character_id).appearance == ""


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


def test_update_character_persists_the_new_words() -> None:
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks="Old."
    )
    update_character(character_id, name="Ida-Rose", kind="toy", marks="New marks.")

    saved = load_character(character_id)
    assert saved.name == "Ida-Rose"
    assert saved.kind == "toy"
    assert saved.marks == "New marks."
    # Neither picture is touched by a word-only edit.
    assert load_character_image(character_id) == PORTRAIT
    assert load_character_image(character_id, portrait=False) == PHOTO


def test_update_character_corrects_a_wrong_appearance() -> None:
    # A model's guess about a child's colouring must be as correctable as
    # any other word a parent typed.
    character_id = save_character(
        photo=PHOTO,
        portrait=PORTRAIT,
        name="Ida",
        kind="person",
        marks="",
        appearance="Blonde hair, blue eyes, pale skin.",
    )
    update_character(
        character_id,
        name="Ida",
        kind="person",
        marks="",
        appearance="Brown hair, brown eyes, light-brown skin.",
    )
    assert load_character(character_id).appearance == (
        "Brown hair, brown eyes, light-brown skin."
    )


def test_update_character_fills_in_a_blank_appearance_with_no_reupload() -> None:
    # The exact repair an existing character with no description needs: the
    # photograph is untouched, only the words are added.
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks=""
    )
    assert load_character(character_id).appearance == ""

    update_character(
        character_id,
        name="Ida",
        kind="person",
        marks="",
        appearance="Brown eyes, dark hair, light-brown skin.",
    )

    saved = load_character(character_id)
    assert saved.appearance == "Brown eyes, dark hair, light-brown skin."
    assert load_character_image(character_id, portrait=False) == PHOTO


def test_update_character_rejects_a_blank_name() -> None:
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks=""
    )
    with pytest.raises(ValueError):
        update_character(character_id, name="   ", kind="person", marks="")
    assert load_character(character_id).name == "Ida"


def test_update_character_rejects_an_unknown_kind() -> None:
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks=""
    )
    with pytest.raises(ValueError):
        update_character(character_id, name="Ida", kind="dragon", marks="")
    assert load_character(character_id).kind == "person"


def test_update_character_portrait_replaces_only_the_portrait() -> None:
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks=""
    )
    new_portrait = PORTRAIT + b"-redrawn"
    update_character_portrait(character_id, new_portrait)

    assert load_character_image(character_id) == new_portrait
    assert load_character_image(character_id, portrait=False) == PHOTO
    assert [c.id for c in list_characters()] == [character_id]


def test_load_character_portrait_returns_none_for_a_corrupt_file() -> None:
    # FB-02's storage-layer half: a decode failure must come back as None,
    # not as an exception the caller has to know to catch.
    character_id = save_character(
        photo=PHOTO, portrait=_real_png(), name="Ida", kind="person", marks=""
    )
    (characters_root() / character_id / "portrait.png").write_bytes(b"")
    assert load_character_portrait(character_id) is None


def test_load_character_portrait_returns_the_bytes_for_a_real_image() -> None:
    real_portrait = _real_png()
    character_id = save_character(
        photo=PHOTO, portrait=real_portrait, name="Ida", kind="person", marks=""
    )
    assert load_character_portrait(character_id) == real_portrait
