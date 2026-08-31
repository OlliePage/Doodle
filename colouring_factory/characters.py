from __future__ import annotations

import json
import shutil
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .storage import data_root

# A person gets the rules about faces and hair; a toy gets told to keep its worn
# patches and its odd button; a character (an existing design, such as a
# cartoon) gets told to keep its own particular design rather than a generic
# version of the idea of it. See TOY_LIKENESS_RULE and NAMED_CHARACTER_RULE
# in prompts.py.
CHARACTER_KINDS = ("person", "toy", "character")


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    kind: str
    marks: str
    created_at: str
    # What a model saw in the photograph the one time it was asked: hair,
    # eyes, skin and the like. Kept apart from `marks`, which a parent types
    # freely and which drives likeness (shape) rather than colour — see
    # colouring_factory/appearance.py and build_colour_suggestion_prompt.
    appearance: str = ""


def characters_root() -> Path:
    path = data_root() / "characters"
    path.mkdir(parents=True, exist_ok=True)
    return path


# save_character writes photo.png, portrait.png and character.json in that
# order under a folder named with this prefix, then moves the whole folder
# into place under the character's own id with one atomic rename. A crash
# between any two of those writes therefore never leaves a folder holding
# the child's photo under the id list_characters and the delete button both
# resolve by — it leaves one under this prefix instead, which _sweep_stray
# below clears out the next time anyone reads the store.
_STAGING_PREFIX = ".incoming-"


def _sweep_stray_saves(root: Path) -> None:
    """Clear a staging folder an earlier save never finished moving into
    place — the process-killed half of the atomic-save guarantee that the
    `except` in save_character cannot cover, since a kill leaves no
    exception to catch. A script run in this app is single-threaded, so a
    folder still here when this runs is a crash, never a save genuinely in
    flight."""

    for entry in root.iterdir():
        if entry.is_dir() and entry.name.startswith(_STAGING_PREFIX):
            shutil.rmtree(entry, ignore_errors=True)


def save_character(
    *,
    photo: bytes,
    portrait: bytes,
    name: str,
    kind: str,
    marks: str,
    appearance: str = "",
) -> str:
    name = name.strip()
    if not name:
        raise ValueError("A character needs a name.")
    if kind not in CHARACTER_KINDS:
        raise ValueError(f"Unknown kind of character: {kind}")
    if not photo or not portrait:
        raise ValueError("A character needs both a picture and a portrait.")

    # Microseconds, not seconds: three characters added in one second still sort.
    character_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    root = characters_root()
    staging = root / f"{_STAGING_PREFIX}{character_id}"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        (staging / "photo.png").write_bytes(photo)
        (staging / "portrait.png").write_bytes(portrait)
        (staging / "character.json").write_text(
            json.dumps(
                {
                    "id": character_id,
                    "name": name,
                    "kind": kind,
                    "marks": marks.strip(),
                    "appearance": appearance.strip(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        staging.replace(root / character_id)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return character_id


def update_character(
    character_id: str, *, name: str, kind: str, marks: str, appearance: str = ""
) -> None:
    """Correct a saved character's words without touching either picture.

    The id and created_at are read from the existing file and kept as they
    are: this is a repair to what a parent typed, not a new character. That
    includes appearance: a model's guess about a child's colouring must be
    as correctable as any word the parent typed themselves, and filling one
    in for a character saved before this field existed is this same repair,
    not a fresh upload.
    """

    name = name.strip()
    if not name:
        raise ValueError("A character needs a name.")
    if kind not in CHARACTER_KINDS:
        raise ValueError(f"Unknown kind of character: {kind}")

    folder = _folder_for(character_id)
    path = folder / "character.json"
    try:
        payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FileNotFoundError(f"Character {character_id} was not found.") from exc

    payload["name"] = name
    payload["kind"] = kind
    payload["marks"] = marks.strip()
    payload["appearance"] = appearance.strip()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def update_character_portrait(character_id: str, portrait: bytes) -> None:
    """Replace a character's portrait, the photograph and everything else
    about them left untouched — the redraw half of the repair, for when a
    drawing misses rather than the words describing it."""

    if not portrait:
        raise ValueError("A character needs a portrait.")
    folder = _folder_for(character_id)
    if not folder.exists():
        raise FileNotFoundError(f"Character {character_id} was not found.")
    (folder / "portrait.png").write_bytes(portrait)


def _read(folder: Path) -> Character | None:
    try:
        payload: dict[str, Any] = json.loads(
            (folder / "character.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not (folder / "portrait.png").exists():
        return None

    # Read through, the way quick_drawing_options does, so a hand-edited file
    # still yields something drawable rather than crashing the homepage.
    kind = str(payload.get("kind", "person"))
    return Character(
        # The folder name, not the JSON's own "id" field: _folder_for,
        # delete_character and every path lookup resolve by folder name, so
        # a hand-edited id that disagrees with it must never be trusted —
        # that disagreement is exactly how DATA-03 made a record vanish from
        # every listing with no error.
        id=folder.name,
        name=str(payload.get("name", "")).strip() or "Someone",
        kind=kind if kind in CHARACTER_KINDS else "person",
        marks=str(payload.get("marks", "")),
        created_at=str(payload.get("created_at", "")),
        # Missing on every character saved before this field existed, so a
        # blank default is the ordinary case, not a corrupt record.
        appearance=str(payload.get("appearance", "")),
    )


def list_characters() -> list[Character]:
    root = characters_root()
    _sweep_stray_saves(root)
    found: list[Character] = []
    for folder in root.iterdir():
        if not folder.is_dir():
            continue
        character = _read(folder)
        if character is not None:
            found.append(character)
    return sorted(found, key=lambda character: character.created_at, reverse=True)


def _mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def characters_signature() -> tuple[tuple[str, int, int], ...]:
    """A cheap fingerprint of the whole store's current state.

    app.py reruns whichever screen lists or thumbnails characters on every
    interaction anywhere on it — Streamlit's own model, not a bug in this
    feature — so caching those reads (a full JSON parse and, for a
    thumbnail, a full PNG decode, per character) needs a way to know when to
    invalidate that costs far less than the read itself. One stat() call per
    file, no open, no parse, no decode, changes on exactly the occasions
    that matter: a folder's own timestamp on an add or a delete,
    character.json's or portrait.png's on an edit or a redraw. Trusting the
    real filesystem here rather than a counter this module would have to
    remember to bump at every call site also means a character saved
    directly (as every test in this file does, and as a future caller might)
    is picked up correctly with no extra wiring.
    """

    root = characters_root()
    signature = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir():
            continue
        signature.append(
            (
                folder.name,
                _mtime_ns(folder / "character.json"),
                _mtime_ns(folder / "portrait.png"),
            )
        )
    return tuple(signature)


def load_character(character_id: str) -> Character:
    character = _read(_folder_for(character_id))
    if character is None:
        raise FileNotFoundError(f"Character {character_id} was not found.")
    return character


def load_character_image(character_id: str, *, portrait: bool = True) -> bytes:
    chosen = _folder_for(character_id) / ("portrait.png" if portrait else "photo.png")
    if not chosen.exists():
        raise FileNotFoundError(f"Character {character_id} has no such picture.")
    return chosen.read_bytes()


def character_portrait_mtime(character_id: str) -> int:
    """The portrait file's own modification time, for cache-busting a
    decoded copy of it without reading or decoding the file to check."""

    return _mtime_ns(_folder_for(character_id) / "portrait.png")


def load_character_portrait(character_id: str) -> bytes | None:
    """The portrait's bytes, or None when they cannot be shown as a picture.

    A cloud-sync client can leave a zero-byte placeholder for a file it has
    not finished downloading, and a disk fault can truncate one outright.
    Either way the bytes exist but Pillow cannot decode them, and that
    decode used to happen for the first time deep inside st.image, where the
    resulting exception took the whole characters screen down with it —
    every character sorted after the bad one, and the add form, gone. This
    is the one place that check belongs, so the screen can degrade one card
    to a placeholder instead.
    """

    try:
        data = load_character_image(character_id)
    except FileNotFoundError:
        return None
    try:
        with Image.open(BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError):
        return None
    return data


def delete_character(character_id: str) -> None:
    folder = _folder_for(character_id)
    if folder.exists():
        shutil.rmtree(folder)


def resolve_cast(
    character_ids: Sequence[str], characters: Sequence[Character]
) -> list[tuple[str, str, str, str, str]]:
    """Character ids resolved against who is actually still saved.

    Read-through, the same discipline quick_drawing_options applies to the
    saved settings: an id that no longer matches a character (because it was
    deleted since) is dropped here rather than reaching load_character_image
    and breaking the caller. `characters` is supplied by the caller rather
    than read here, so a cached or uncached list works identically.
    """

    by_id = {character.id: character for character in characters}
    return [
        (
            character.id,
            character.name,
            character.kind,
            character.marks,
            character.appearance,
        )
        for character_id in character_ids
        if (character := by_id.get(character_id)) is not None
    ]


def toggle_chosen(
    chosen: Sequence[str], character_id: str, *, ticked: bool
) -> list[str]:
    """One id added or removed from a chosen list, order otherwise kept.

    Keyed by id, not name: two characters can share a name (a girl and her
    teddy both called Ida), and a name-keyed widget key raised a duplicate-
    key error that took the whole homepage down with it.
    """

    updated = list(chosen)
    if ticked:
        if character_id not in updated:
            updated.append(character_id)
    elif character_id in updated:
        updated.remove(character_id)
    return updated


def _folder_for(character_id: str) -> Path:
    root = characters_root().resolve()
    folder = (characters_root() / character_id).resolve()
    if root not in folder.parents:
        raise ValueError("Invalid character path.")
    return folder
