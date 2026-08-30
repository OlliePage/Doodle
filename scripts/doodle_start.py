"""Everything Doodle needs before it can draw, and then the app itself.

Run through `make doodle`. Stdlib only, and deliberately so: this runs before
the virtual environment is guaranteed to exist, under whatever Python the Mac
happens to have, so it cannot depend on anything Doodle installs.

The sequence is the one that kept going wrong by hand. Bring the checkout up
to date without ever touching uncommitted work; make sure the environment and
its packages exist; say which drawing services have a key; clear the port,
because an app started before an update keeps the old code in memory and fails
on functions that are sitting right there in the file; then hand the terminal
over to Streamlit.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VENV = REPO / ".venv"
PORT = 8501

# Imported, not pip-listed, because a package's import name is what actually
# has to work: Pillow imports as PIL and PyMuPDF as fitz.
RUNTIME_IMPORTS = (
    "streamlit",
    "openai",
    "PIL",
    "reportlab",
    "fitz",
    "pypdf",
    "watchdog",
)

PROVIDERS = ("openai", "google", "recraft")

TOTAL_STEPS = 5


def say(step: int, message: str) -> None:
    print(f"[{step}/{TOTAL_STEPS}] {message}", flush=True)


def detail(message: str) -> None:
    print(f"      {message}", flush=True)


def capture(command: list[str]) -> str:
    result = subprocess.run(
        command, cwd=REPO, capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def run(command: list[str], *, check: bool = True) -> int:
    result = subprocess.run(command, cwd=REPO, check=False)
    if check and result.returncode != 0:
        raise SystemExit(
            f"That step failed: {' '.join(command)}\nNothing has been launched."
        )
    return result.returncode


def update_plan(branch: str, dirty: bool, behind: int) -> tuple[str, str]:
    """Decide whether it is safe to fast-forward, and say why in English.

    Pulling is only ever safe when there is nothing of yours to lose. Edits in
    progress and any branch other than main both mean the launcher leaves the
    checkout exactly as it found it.
    """

    if dirty:
        return (
            "skip-dirty",
            "You have edits to tracked files, so nothing was pulled. Commit or "
            "set them aside first if you want the latest code.",
        )
    if branch != "main":
        return (
            "skip-branch",
            f"You are on the branch {branch}, not main, so nothing was pulled.",
        )
    if behind == 0:
        return "up-to-date", "Already up to date with GitHub."
    plural = "" if behind == 1 else "s"
    return "pull", f"Bringing in {behind} new commit{plural} from GitHub."


def update_checkout() -> None:
    say(1, "Checking for new code")
    if not (REPO / ".git").exists():
        detail("This is not a git checkout, so there is nothing to update.")
        return

    branch = capture(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"
    # Untracked files are excluded deliberately. A folder git has never heard
    # of cannot be lost to a fast-forward, and counting them stopped the pull
    # for good on a checkout carrying .claude and .agents: every launch said
    # "you have uncommitted changes" about files nobody had edited.
    changes = capture(["git", "status", "--porcelain", "--untracked-files=no"])
    if subprocess.run(
        ["git", "fetch", "origin", "--quiet"], cwd=REPO, check=False
    ).returncode:
        detail("Could not reach GitHub, carrying on with the code you have.")
        return

    behind_text = capture(["git", "rev-list", "--count", "HEAD..origin/main"])
    behind = int(behind_text) if behind_text.isdigit() else 0

    action, message = update_plan(branch, bool(changes), behind)
    detail(message)
    if action == "skip-dirty":
        for line in changes.splitlines():
            detail(f"  {line}")
    if action != "pull":
        return

    for line in capture(
        ["git", "log", "--oneline", f"-{behind}", "origin/main"]
    ).splitlines():
        detail(f"  {line}")
    run(["git", "merge", "--ff-only", "origin/main"])


def venv_python() -> Path:
    return VENV / "bin" / "python"


def silent(command: list[str]) -> int:
    return subprocess.run(
        command, cwd=REPO, capture_output=True, text=True, check=False
    ).returncode


def ensure_environment() -> Path:
    say(2, "Checking the Python environment")
    python = venv_python()
    if not python.exists():
        detail("Creating .venv, which takes a moment the first time.")
        run([sys.executable, "-m", "venv", str(VENV)])

    # An environment made by uv has no pip in it, and nothing later repairs
    # that, so installing Doodle's packages fails on a folder that looks
    # perfectly healthy from the outside.
    if silent([str(python), "-m", "pip", "--version"]):
        detail("This environment has no installer in it; adding one.")
        if silent([str(python), "-m", "ensurepip", "--upgrade"]):
            raise SystemExit(
                f"Could not add pip to {VENV}.\n"
                "Delete that folder and run make doodle again."
            )
        silent([str(python), "-m", "pip", "install", "--upgrade", "--quiet", "pip"])

    detail(f"Using {python}")
    return python


def ensure_dependencies(python: Path) -> None:
    say(3, "Checking Doodle's packages")
    probe = "import " + ", ".join(RUNTIME_IMPORTS)
    if silent([str(python), "-c", probe]) == 0:
        detail("All present.")
        return

    detail("Installing what is missing from requirements.txt.")
    run([str(python), "-m", "pip", "install", "--quiet", "-r", "requirements.txt"])
    if silent([str(python), "-c", probe]):
        raise SystemExit(
            "Doodle's packages still will not import after installing them.\n"
            "Delete the .venv folder and run make doodle again."
        )


# Asked of the app's own code rather than reimplemented here, so there is one
# answer to where a key lives: this session, an environment variable, or the
# file Doodle wrote on this Mac.
KEY_REPORT = """
import json
from colouring_factory.credentials import resolve_provider_key
from colouring_factory.providers import get_provider

found = dict()
for provider_id in __PROVIDERS__:
    key, source = resolve_provider_key(provider_id)
    if key:
        found[get_provider(provider_id).label] = source
print(json.dumps(found))
"""


def report_keys(python: Path) -> None:
    say(4, "Checking your drawing services")
    result = subprocess.run(
        [str(python), "-c", KEY_REPORT.replace("__PROVIDERS__", repr(PROVIDERS))],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        found = json.loads(result.stdout.strip() or "{}")
    except ValueError:
        detail("Could not read the saved keys; Doodle will ask for one if it needs it.")
        return

    if not found:
        detail(
            "No API key yet. Doodle will open on its setup page and walk you "
            "through adding one; Google Gemini has a free allowance."
        )
        return
    for label, source in found.items():
        detail(f"{label}: key found in {source}.")


def port_holders(port: int) -> list[str]:
    """The processes serving this port, and only those.

    Without the listening filter, lsof also reports every browser tab with the
    page open, so stopping "what is on port 8501" would have killed Arc.
    """

    result = subprocess.run(
        ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
        capture_output=True,
        text=True,
        check=False,
    )
    return [line for line in result.stdout.split() if line.strip()]


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def next_free_port(start: int, limit: int = 20) -> int:
    for candidate in range(start, start + limit):
        if port_is_free(candidate):
            return candidate
    raise SystemExit(
        f"Ports {start} to {start + limit - 1} are all busy. "
        "Close something and try again."
    )


def clear_the_port(*, assume_yes: bool) -> int:
    say(5, f"Clearing port {PORT}")
    if port_is_free(PORT):
        detail("Nothing in the way.")
        return PORT

    holders = port_holders(PORT)
    detail(
        "Doodle is already running there. Streamlit re-reads app.py on every "
        "click but keeps the files it imported at startup, so an app left "
        "running through an update ends up calling new code from old modules "
        "and fails on functions that are sitting right there in the file."
    )
    if holders:
        detail(f"Process {', '.join(holders)} is holding the port.")

    if assume_yes or not sys.stdin.isatty():
        answer = "y" if assume_yes else "n"
    else:
        answer = input("      Stop it and start fresh? [Y/n] ").strip().lower() or "y"

    if not answer.startswith("y"):
        spare = next_free_port(PORT + 1)
        detail(f"Leaving it alone. Starting this one on port {spare} instead.")
        return spare

    for pid in holders:
        subprocess.run(["kill", pid], check=False)
    for _ in range(20):
        if port_is_free(PORT):
            detail("Stopped.")
            return PORT

        time.sleep(0.25)

    spare = next_free_port(PORT + 1)
    detail(f"It would not stop. Starting this one on port {spare} instead.")
    return spare


def launch(python: Path, port: int) -> None:
    print(f"\nOpening Doodle on http://localhost:{port}\n", flush=True)
    os.chdir(REPO)
    # Replace this process rather than nesting one inside it, so Control-C in
    # the terminal reaches Streamlit itself.
    os.execv(
        str(python),
        [
            str(python),
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.port",
            str(port),
        ],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Run every check and report, but do not open the app.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Stop an app already on the port without asking.",
    )
    arguments = parser.parse_args()

    update_checkout()
    python = ensure_environment()
    ensure_dependencies(python)
    report_keys(python)

    if arguments.check_only:
        say(5, "Checks only, so nothing was launched.")
        return

    launch(python, clear_the_port(assume_yes=arguments.yes))


if __name__ == "__main__":
    main()
