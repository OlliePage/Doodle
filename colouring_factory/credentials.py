from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Mapping

from .providers import get_provider
from .storage import data_root


def credentials_path() -> Path:
    return data_root() / "credentials.json"


def load_credentials() -> dict[str, str]:
    path = credentials_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return {
        str(provider_id): str(value).strip()
        for provider_id, value in payload.items()
        if isinstance(value, str) and value.strip()
    }


def save_provider_key(provider_id: str, api_key: str) -> None:
    key = api_key.strip()
    if not key:
        raise ValueError("The API key is empty.")

    root = data_root()
    try:
        root.chmod(0o700)
    except OSError:
        pass

    values = load_credentials()
    values[provider_id] = key
    path = credentials_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(values, indent=2), encoding="utf-8")
    try:
        temporary.chmod(0o600)
    except OSError:
        pass
    temporary.replace(path)
    try:
        path.chmod(0o600)
    except OSError:
        pass


def delete_provider_key(provider_id: str) -> None:
    values = load_credentials()
    if provider_id not in values:
        return
    values.pop(provider_id, None)
    path = credentials_path()
    if values:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(values, indent=2), encoding="utf-8")
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(path)
        try:
            path.chmod(0o600)
        except OSError:
            pass
    elif path.exists():
        path.unlink()


def resolve_provider_key(
    provider_id: str,
    session_keys: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    if session_keys:
        session_value = str(session_keys.get(provider_id, "")).strip()
        if session_value:
            return session_value, "this session"

    spec = get_provider(provider_id)
    environment_value = os.getenv(spec.env_var, "").strip()
    if environment_value:
        return environment_value, spec.env_var

    saved_value = load_credentials().get(provider_id, "").strip()
    if saved_value:
        return saved_value, "this Mac"

    return "", ""


def mask_key(api_key: str) -> str:
    key = api_key.strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "••••••••"
    return f"{key[:4]}••••{key[-4:]}"
