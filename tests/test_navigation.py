"""The trail and the browser listener, proven as ordinary Python.

The mechanism itself was proven against a real Chrome in a throwaway app
before this was written; these tests hold the pure logic lifted from it.
"""

from __future__ import annotations

import pytest

from colouring_factory.browser_history import LISTENER_JS, step_script
from colouring_factory.navigation import Trail, place_from_address


def test_going_somewhere_new_after_stepping_back_drops_the_forward_stops() -> None:
    trail = Trail.start("home", session="s")
    trail = trail.go("history")
    trail = trail.go("favourites")

    trail = trail.back()  # now sitting on "history", with "favourites" ahead
    trail = trail.go("studio")

    assert [stop.screen for stop in trail.stops] == ["home", "history", "studio"]
    assert trail.position == 2


def test_tokens_are_never_reused_even_after_back_and_forward_and_go() -> None:
    trail = Trail.start("home", session="s")
    trail = trail.go("history")
    trail = trail.go("favourites")
    dropped_token = trail.here.token  # the "favourites" stop, about to be dropped

    trail = trail.back().back()  # back to "home"
    trail = trail.go("history")  # overwrites the old "history" stop's slot

    tokens = [stop.token for stop in trail.stops]
    assert len(tokens) == len(set(tokens))
    assert dropped_token not in tokens


def test_arrive_with_a_known_token_moves_without_adding_a_stop() -> None:
    trail = Trail.start("home", session="s")
    trail = trail.go("history")
    trail = trail.go("favourites")
    history_token = trail.stops[1].token

    arrived = trail.arrive({"step": history_token})

    assert arrived.position == 1
    assert arrived.here.screen == "history"
    assert arrived.stops == trail.stops


def test_arrive_with_an_unknown_token_starts_afresh_and_keeps_that_token() -> None:
    trail = Trail.start("home", session="s")
    trail = trail.go("history")

    arrived = trail.arrive({"step": "stale-token", "screen": "favourites"})

    assert arrived.stops == (arrived.here,)
    assert arrived.here.screen == "favourites"
    assert arrived.here.token == "stale-token"
    # The issued counter carries on so a token already handed to the browser
    # is never handed out again, even though the trail itself was reset.
    assert arrived.issued == trail.issued


def test_arrive_back_to_the_first_stop_with_no_step_param() -> None:
    trail = Trail.start("home", session="s")  # token defaults to ""
    trail = trail.go("history")

    arrived = trail.arrive({})

    assert arrived.position == 0
    assert arrived.here.screen == "home"
    assert arrived.stops == trail.stops


def test_place_from_address_rejects_unknown_screens_and_doodle_less_results() -> None:
    assert place_from_address({"screen": "nonsense"}) == ("home", "")
    assert place_from_address({}) == ("home", "")
    assert place_from_address({"screen": "result"}) == ("home", "")
    assert place_from_address({"screen": "result", "doodle": "abc"}) == (
        "result",
        "abc",
    )
    # An id edited in the address bar never gets as far as naming a folder.
    assert place_from_address({"screen": "result", "doodle": "../settings"}) == (
        "home",
        "",
    )
    # Only "result" carries a doodle; it is dropped for every other screen.
    assert place_from_address({"screen": "history", "doodle": "abc"}) == ("history", "")


def test_can_go_back_and_forward_at_both_ends() -> None:
    trail = Trail.start("home", session="s")
    assert not trail.can_go_back
    assert not trail.can_go_forward
    with pytest.raises(ValueError):
        trail.back()
    with pytest.raises(ValueError):
        trail.forward()

    trail = trail.go("history")
    assert trail.can_go_back
    assert not trail.can_go_forward
    with pytest.raises(ValueError):
        trail.forward()

    back = trail.back()
    assert not back.can_go_back
    assert back.can_go_forward
    with pytest.raises(ValueError):
        back.back()


def test_step_script_rejects_a_bad_direction_and_a_missing_nonce() -> None:
    with pytest.raises(ValueError):
        step_script("sideways", "s.1")
    with pytest.raises(ValueError):
        step_script("back", "")
    # The nonce lands inside the page's script, so anything able to break out
    # of the string is refused.
    with pytest.raises(ValueError):
        step_script("back", '1"; alert(1); "')

    html = step_script("back", "a1b2c3.3")
    assert "window.history.back()" in html
    assert 'window.__doodleNavNonce = "a1b2c3.3"' in html


def test_listener_js_uses_only_v2_apis() -> None:
    assert "popstate" in LISTENER_JS
    assert "setTriggerValue" in LISTENER_JS
    assert (
        "\n" in LISTENER_JS.strip()
    )  # a single-line string reads as a file path in CCv2
    assert "setComponentValue" not in LISTENER_JS
    assert "window.Streamlit" not in LISTENER_JS
    assert "postMessage" not in LISTENER_JS
