from __future__ import annotations

from dataclasses import dataclass

from .models import GeneratedArtwork


@dataclass(frozen=True)
class Version:
    artwork: GeneratedArtwork
    instruction: str
    parent: int | None


def start(artwork: GeneratedArtwork) -> tuple[Version, ...]:
    """Begin a fresh chain. Any previous chain is abandoned, not merged."""

    return (Version(artwork=artwork, instruction="", parent=None),)


def append(
    chain: tuple[Version, ...],
    artwork: GeneratedArtwork,
    instruction: str,
    parent: int,
) -> tuple[Version, ...]:
    """Add a version derived from `parent`, without disturbing what came after.

    Append-only by design: refining from an earlier version after exploring a
    direction must not delete the direction that was explored.
    """

    instruction = instruction.strip()
    if not instruction:
        raise ValueError("A refinement needs an instruction.")
    if not 0 <= parent < len(chain):
        raise ValueError(f"No version {parent} to refine from.")

    return chain + (Version(artwork=artwork, instruction=instruction, parent=parent),)


def ancestry(chain: tuple[Version, ...], index: int) -> tuple[int, ...]:
    """Indices from the original down to `index`, in order."""

    if not 0 <= index < len(chain):
        raise ValueError(f"No version {index}.")

    line: list[int] = []
    cursor: int | None = index
    while cursor is not None:
        line.append(cursor)
        cursor = chain[cursor].parent
    return tuple(reversed(line))
