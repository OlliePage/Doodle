from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .storage import data_root

# A person gets the rules about faces and hair; a toy gets told to keep its worn
# patches and its odd button. A character is anything else recognisable.
CHARACTER_KINDS = ("person", "toy", "character")


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    kind: str
    marks: str
    created_at: str


def characters_root() -> Path:
    path = data_root() / "characters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_character(
    *, photo: bytes, portrait: bytes, name: str, kind: str, marks: str
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
    folder = characters_root() / character_id
    folder.mkdir(parents=True, exist_ok=False)

    (folder / "photo.png").write_bytes(photo)
    (folder / "portrait.png").write_bytes(portrait)
    (folder / "character.json").write_text(
        json.dumps(
            {
                "id": character_id,
                "name": name,
                "kind": kind,
                "marks": marks.strip(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return character_id


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
        id=str(payload.get("id", folder.name)),
        name=str(payload.get("name", "")).strip() or "Someone",
        kind=kind if kind in CHARACTER_KINDS else "person",
        marks=str(payload.get("marks", "")),
        created_at=str(payload.get("created_at", "")),
    )


def list_characters() -> list[Character]:
    found: list[Character] = []
    for folder in characters_root().iterdir():
        if not folder.is_dir():
            continue
        character = _read(folder)
        if character is not None:
            found.append(character)
    return sorted(found, key=lambda character: character.created_at, reverse=True)


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


def _folder_for(character_id: str) -> Path:
    root = characters_root().resolve()
    folder = (characters_root() / character_id).resolve()
    if root not in folder.parents:
        raise ValueError("Invalid character path.")
    return folder
