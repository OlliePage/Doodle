from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

from colouring_factory import __version__
from colouring_factory import version as version_module


def _clear_cache() -> None:
    version_module.build_revision.cache_clear()


def test_label_carries_the_version() -> None:
    _clear_cache()
    assert version_module.build_label().startswith(f"v{__version__}")


def test_label_uses_the_environment_revision_when_given(monkeypatch) -> None:
    _clear_cache()
    monkeypatch.setenv(version_module.REVISION_ENV_VAR, "deadbee")
    assert version_module.build_label() == f"v{__version__} · deadbee"
    _clear_cache()


def test_label_falls_back_to_version_when_git_is_unavailable(monkeypatch) -> None:
    """A missing git must not take the whole app down on first render."""

    _clear_cache()
    monkeypatch.delenv(version_module.REVISION_ENV_VAR, raising=False)

    def _no_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", _no_git)
    assert version_module.build_label() == f"v{__version__}"
    _clear_cache()


def test_revision_looks_like_a_git_hash_in_this_checkout(monkeypatch) -> None:
    _clear_cache()
    monkeypatch.delenv(version_module.REVISION_ENV_VAR, raising=False)
    revision = version_module.build_revision()
    _clear_cache()
    if revision:
        assert re.fullmatch(r"[0-9a-f]{7,40}", revision)


def test_packaging_version_matches_the_package() -> None:
    """The two are written out separately and would otherwise drift apart."""

    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"][
        "version"
    ]
    assert declared == __version__


def test_badge_renders_in_the_app() -> None:
    """Unit tests cover the label; this covers it actually reaching the page."""

    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(
        str(Path(__file__).resolve().parent.parent / "app.py"),
        default_timeout=60,
    ).run()

    bodies = [element.proto.body for element in app.get("html")]
    badge = next((body for body in bodies if "doodle-build" in body), None)
    assert badge is not None, "version badge missing from the rendered app"
    assert f"v{__version__}" in badge
    assert "position: fixed" in badge
    assert "pointer-events: none" in badge
