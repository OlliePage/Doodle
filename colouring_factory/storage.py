from __future__ import annotations

import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .prompts import STYLE_PRESETS


def data_root() -> Path:
    override = os.getenv("DOODLE_DATA_DIR") or os.getenv("COLOURING_FACTORY_DATA_DIR")
    if override:
        root = Path(override).expanduser()
    else:
        preferred = Path.home() / ".doodle"
        legacy = Path.home() / ".colouring_factory"
        # Preserve an existing library when upgrading from the first MVP.
        root = legacy if legacy.exists() and not preferred.exists() else preferred
    root.mkdir(parents=True, exist_ok=True)
    return root


def library_root() -> Path:
    path = data_root() / "library"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return data_root() / "settings.json"


def _new_item_id() -> str:
    return (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )


def _item_folder(item_id: str) -> Path:
    folder = library_root() / item_id
    root = library_root().resolve()
    resolved = folder.resolve()
    if root not in resolved.parents:
        raise ValueError("Invalid library item path.")
    return folder


def _read_metadata(folder: Path) -> dict[str, Any]:
    return json.loads((folder / "metadata.json").read_text(encoding="utf-8"))


def _write_metadata(folder: Path, payload: dict[str, Any]) -> None:
    path = folder / "metadata.json"
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def save_library_item(
    *,
    processed_image: bytes,
    raw_image: bytes | None,
    title: str,
    metadata: dict[str, Any],
) -> str:
    item_id = _new_item_id()
    folder = library_root() / item_id
    folder.mkdir(parents=True, exist_ok=False)

    (folder / "processed.png").write_bytes(processed_image)
    if raw_image:
        (folder / "raw.png").write_bytes(raw_image)

    payload = {
        "id": item_id,
        "title": title.strip() or "Untitled artwork",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "favourite": True,
    }
    _write_metadata(folder, payload)
    return item_id


def record_doodle(
    *,
    raw_image: bytes,
    processed_image: bytes,
    title: str,
    metadata: dict[str, Any],
) -> str:
    raw_sha256 = hashlib.sha256(raw_image).hexdigest()
    for item in list_library_items():
        if item.get("raw_sha256") == raw_sha256:
            return item["id"]

    item_id = _new_item_id()
    folder = library_root() / item_id
    folder.mkdir(parents=True, exist_ok=False)

    (folder / "processed.png").write_bytes(processed_image)
    (folder / "raw.png").write_bytes(raw_image)

    payload = {
        "id": item_id,
        "title": title.strip() or "Untitled artwork",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "favourite": False,
        "raw_sha256": raw_sha256,
    }
    _write_metadata(folder, payload)
    return item_id


def is_favourite(item: dict[str, Any]) -> bool:
    # An entry with no favourite key was saved by hand before history
    # existed, so it counts as a favourite.
    return item.get("favourite", True)


def set_favourite(item_id: str, favourite: bool) -> None:
    folder = _item_folder(item_id)
    payload = _read_metadata(folder)
    payload["favourite"] = favourite
    _write_metadata(folder, payload)


def update_doodle(
    item_id: str,
    *,
    title: str | None = None,
    processed_image: bytes | None = None,
) -> None:
    folder = _item_folder(item_id)
    payload = _read_metadata(folder)
    if title is not None:
        payload["title"] = title.strip() or "Untitled artwork"
    if processed_image is not None:
        (folder / "processed.png").write_bytes(processed_image)
    _write_metadata(folder, payload)


def attach_pair(item_id: str, *, raw_image: bytes, processed_image: bytes) -> None:
    folder = _item_folder(item_id)
    (folder / "pair_raw.png").write_bytes(raw_image)
    (folder / "pair.png").write_bytes(processed_image)


def load_doodle(item_id: str) -> dict[str, Any] | None:
    folder = _item_folder(item_id)
    metadata_file = folder / "metadata.json"
    processed_file = folder / "processed.png"
    if not metadata_file.exists() or not processed_file.exists():
        return None

    payload = _read_metadata(folder)
    raw_file = folder / "raw.png"
    pair_raw_file = folder / "pair_raw.png"
    payload["raw"] = (raw_file if raw_file.exists() else processed_file).read_bytes()
    payload["processed"] = processed_file.read_bytes()
    payload["pair_raw"] = pair_raw_file.read_bytes() if pair_raw_file.exists() else None
    return payload


def list_library_items(*, favourites_only: bool = False) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for folder in library_root().iterdir():
        if not folder.is_dir():
            continue
        metadata_file = folder / "metadata.json"
        processed_file = folder / "processed.png"
        if not metadata_file.exists() or not processed_file.exists():
            continue
        try:
            item = json.loads(metadata_file.read_text(encoding="utf-8"))
            item["processed_path"] = str(processed_file)
            raw_path = folder / "raw.png"
            item["raw_path"] = str(raw_path) if raw_path.exists() else None
            if favourites_only and not is_favourite(item):
                continue
            items.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


def load_library_image(item_id: str, prefer_raw: bool = False) -> bytes:
    folder = library_root() / item_id
    chosen = folder / (
        "raw.png" if prefer_raw and (folder / "raw.png").exists() else "processed.png"
    )
    if not chosen.exists():
        raise FileNotFoundError(f"Library item {item_id} was not found.")
    return chosen.read_bytes()


def delete_library_item(item_id: str) -> None:
    folder = _item_folder(item_id)
    if folder.exists():
        shutil.rmtree(folder)


def clear_history_keep_favourites() -> int:
    cleared = 0
    for item in list_library_items():
        if is_favourite(item):
            continue
        delete_library_item(item["id"])
        cleared += 1
    return cleared


def load_settings() -> dict[str, Any]:
    path = settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_settings(settings: dict[str, Any]) -> None:
    path = settings_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    temporary.replace(path)


# The homepage asks these three questions before it draws, and remembers the
# answers, because a parent drawing for the same two children wants the same
# answers every time. Read through here so a settings file written by an older
# version, or edited by hand, still yields something the app can draw with.
QUICK_ALTERNATIVE_CHOICES = (1, 2, 3, 4)
QUICK_AGE_CHOICES = ("2-3 years", "4-5 years", "6-9 years", "Grown-up")
GROWN_UP_LEVEL = "Grown-up"
# Derived, never re-typed. This tuple used to duplicate the STYLE_PRESETS keys
# by hand with nothing keeping the two in step, so a rename in one file offered
# a style the prompt builder silently ignored in favour of its fallback. The
# first entry matters twice over: it is the homepage default, and it is what an
# unrecognised saved style is quietly rewritten to.
QUICK_STYLE_CHOICES = tuple(STYLE_PRESETS)


def quick_drawing_options(settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or {}

    try:
        alternatives = int(settings.get("quick_alternatives", 1))
    except (TypeError, ValueError):
        alternatives = 1
    if alternatives not in QUICK_ALTERNATIVE_CHOICES:
        alternatives = 1

    age_profile = str(settings.get("quick_age_profile", QUICK_AGE_CHOICES[0]))
    if age_profile not in QUICK_AGE_CHOICES:
        age_profile = QUICK_AGE_CHOICES[0]

    style = str(settings.get("quick_style", QUICK_STYLE_CHOICES[0]))
    if style not in QUICK_STYLE_CHOICES:
        style = QUICK_STYLE_CHOICES[0]

    # A grown-up drawing for themselves has nothing to pair with, so the answer
    # is no whatever the settings file says.
    pair_grown_up = bool(settings.get("quick_pair_grown_up", False)) and (
        age_profile != GROWN_UP_LEVEL
    )

    return {
        "alternatives": alternatives,
        "age_profile": age_profile,
        "style": style,
        "pair_grown_up": pair_grown_up,
    }
