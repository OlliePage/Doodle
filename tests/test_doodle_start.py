"""The startup sequence behind `make doodle`.

Two things about this script have to hold, and neither is visible by reading
it: it must never pull over work in progress, and it must run under a bare
system Python, because it is what creates the environment everything else
needs.
"""

from __future__ import annotations

import ast
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "doodle_start.py"
MAKEFILE = PROJECT_ROOT / "Makefile"


@pytest.fixture(scope="module")
def launcher():
    spec = importlib.util.spec_from_file_location("doodle_start", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_uncommitted_work_is_never_pulled_over(launcher) -> None:
    action, message = launcher.update_plan("main", dirty=True, behind=3)
    assert action == "skip-dirty"
    assert "uncommitted" in message


def test_a_branch_is_left_alone(launcher) -> None:
    action, message = launcher.update_plan("claude/make-doodle", dirty=False, behind=2)
    assert action == "skip-branch"
    assert "claude/make-doodle" in message


def test_a_clean_main_behind_origin_is_fast_forwarded(launcher) -> None:
    action, message = launcher.update_plan("main", dirty=False, behind=1)
    assert action == "pull"
    assert "1 new commit from GitHub" in message

    _, plural = launcher.update_plan("main", dirty=False, behind=4)
    assert "4 new commits" in plural


def test_nothing_to_do_says_so(launcher) -> None:
    action, message = launcher.update_plan("main", dirty=False, behind=0)
    assert action == "up-to-date"
    assert "up to date" in message


def test_a_busy_port_moves_the_app_rather_than_failing(launcher, monkeypatch) -> None:
    monkeypatch.setattr(launcher, "port_is_free", lambda port: port != 8501)
    assert launcher.next_free_port(8502) == 8502
    assert launcher.next_free_port(8501) == 8502


def test_only_the_server_on_the_port_is_ever_stopped(launcher, monkeypatch) -> None:
    """A browser with the app open also holds the port.

    The first version asked lsof for everything on 8501 and offered to stop it,
    which on a real machine listed Arc alongside Streamlit. Answering yes would
    have killed the browser.
    """

    seen: list[list[str]] = []

    class Result:
        stdout = "93040\n"

    def fake_run(command, **kwargs):
        seen.append(command)
        return Result()

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    assert launcher.port_holders(8501) == ["93040"]
    assert "-sTCP:LISTEN" in seen[0]


def test_the_launcher_runs_on_a_bare_python() -> None:
    """No import outside the standard library, checked by reading the source.

    It runs before .venv exists, so a single third-party import would make the
    command that installs Doodle's packages depend on Doodle's packages.
    """

    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imported.add(node.module.split(".")[0])

    outside = imported - set(sys.stdlib_module_names)
    assert not outside, f"the launcher imports {sorted(outside)}"


def test_nothing_in_the_makefile_kills_a_browser() -> None:
    """The same rule as port_holders, in the language make actually runs.

    The stop target was written without the filter and killed an Arc process
    that had the app open, so this is checked in both places.
    """

    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        command = line.split("#", 1)[0]
        if "lsof" in command:
            assert "-sTCP:LISTEN" in command, line.strip()


def test_make_doodle_runs_the_launcher() -> None:
    body = MAKEFILE.read_text(encoding="utf-8")
    assert "\ndoodle:" in body
    assert "scripts/doodle_start.py" in body

    listed = subprocess.run(
        ["make", "-n", "doodle"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "scripts/doodle_start.py" in listed.stdout
