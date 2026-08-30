from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def save_library_item(
    *,
    processed_image: bytes,
    raw_image: bytes | None,
    title: str,
    metadata: dict[str, Any],
) -> str:
    item_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
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
    }
    (folder / "metadata.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return item_id


def list_library_items() -> list[dict[str, Any]]:
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
            items.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    return sorted(items, key=lambda item: item.get("created_at", ""), reverse=True)


def load_library_image(item_id: str, prefer_raw: bool = False) -> bytes:
    folder = library_root() / item_id
    chosen = folder / ("raw.png" if prefer_raw and (folder / "raw.png").exists() else "processed.png")
    if not chosen.exists():
        raise FileNotFoundError(f"Library item {item_id} was not found.")
    return chosen.read_bytes()


def delete_library_item(item_id: str) -> None:
    folder = library_root() / item_id
    root = library_root().resolve()
    resolved = folder.resolve()
    if root not in resolved.parents:
        raise ValueError("Invalid library item path.")
    if folder.exists():
        shutil.rmtree(folder)


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
