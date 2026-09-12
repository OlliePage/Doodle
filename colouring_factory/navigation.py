"""The trail behind Back, Forward and the browser's own history buttons.

Pure logic, no Streamlit: kept testable as ordinary Python and driven by
``app.py``. See the "Navigation" section of
``docs/superpowers/specs/2026-09-12-history-favourites-navigation-design.md``
for the model this encodes.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace

# The drawing screen and the connection screen never get an address of their
# own — no Back or Forward can land there and pay for a picture again.
DETOURS = frozenset({"generate", "connect"})

# Screens a fresh page load or an unrecognised browser address may open.
RESTORABLE = frozenset(
    {"home", "result", "history", "favourites", "characters", "studio"}
)


@dataclass(frozen=True)
class Stop:
    token: str
    screen: str
    doodle: str = ""


@dataclass(frozen=True)
class Trail:
    stops: tuple[Stop, ...]
    position: int
    session: str
    issued: int

    @classmethod
    def start(
        cls, screen: str, doodle: str = "", *, session: str, token: str = ""
    ) -> "Trail":
        return cls(
            stops=(Stop(token, screen, doodle),), position=0, session=session, issued=0
        )

    @property
    def here(self) -> Stop:
        return self.stops[self.position]

    @property
    def can_go_back(self) -> bool:
        return self.position > 0

    @property
    def can_go_forward(self) -> bool:
        return self.position < len(self.stops) - 1

    def back(self) -> "Trail":
        if not self.can_go_back:
            raise ValueError("There is nowhere back to go.")
        return replace(self, position=self.position - 1)

    def forward(self) -> "Trail":
        if not self.can_go_forward:
            raise ValueError("There is nowhere forward to go.")
        return replace(self, position=self.position + 1)

    def go(self, screen: str, doodle: str = "") -> "Trail":
        # A move from mid-trail (after Back) drops everything ahead, the way a
        # browser drops forward history once you navigate somewhere new.
        token = f"{self.session}.{self.issued}"
        stops = self.stops[: self.position + 1] + (Stop(token, screen, doodle),)
        return replace(
            self, stops=stops, position=len(stops) - 1, issued=self.issued + 1
        )

    def arrive(self, params: Mapping[str, str]) -> "Trail":
        token = params.get("step", "")
        index = next(
            (i for i, stop in enumerate(self.stops) if stop.token == token), None
        )
        if index is not None:
            return replace(self, position=index)
        # An unknown token (a tab refreshed earlier) starts a fresh trail from
        # the address, but keeps the session's issued counter running so a
        # token already handed to the browser is never handed out again.
        screen, doodle = place_from_address(params)
        fresh = Trail.start(screen, doodle, session=self.session, token=token)
        return replace(fresh, issued=self.issued)

    def address(self) -> dict[str, str]:
        stop = self.here
        address = {"screen": stop.screen, "step": stop.token}
        if stop.doodle:
            address["doodle"] = stop.doodle
        return address


def place_from_address(params: Mapping[str, str]) -> tuple[str, str]:
    screen = params.get("screen", "home")
    if screen not in RESTORABLE:
        return "home", ""
    if screen != "result":
        return screen, ""
    doodle = params.get("doodle", "")
    if not doodle:
        return "home", ""
    return "result", doodle
