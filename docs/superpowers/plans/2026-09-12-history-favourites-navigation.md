# History, favourites and navigation — implementation plan

Spec: `docs/superpowers/specs/2026-09-12-history-favourites-navigation-design.md`.
Branch `claude/history-favourites-nav`. Tests: `.venv/bin/python -m pytest`
(~90 s, green at the start on 2026-09-12). A formatter runs after every edit and
strips unused imports, so add an import in the same edit as its first use.

Tasks 1 and 2 touch separate files and can run side by side. Tasks 3 and 4 both
rewrite `app.py` and run in order after them.

## Task 1 — the store learns history and favourites

Files: `colouring_factory/storage.py`, `tests/test_storage.py`, new `tests/conftest.py`.

- [x] `tests/conftest.py`: an autouse fixture setting `DOODLE_DATA_DIR` to a
      per-test `tmp_path` folder, so no test can write into the real `~/.doodle`.
- [x] `record_doodle(*, raw_image, processed_image, title, metadata) -> str`:
      returns the id of an existing entry whose `raw_sha256` matches the raw
      bytes; otherwise writes a new entry exactly as `save_library_item` does,
      plus `favourite: false` and `raw_sha256`. Serialise metadata with
      `default=str` so an odd value never loses a picture.
- [x] `is_favourite(item) -> bool`: `item.get("favourite", True)` — an entry
      without the key was saved by hand before history existed.
- [x] `set_favourite(item_id, favourite)`, `update_doodle(item_id, *, title=None,
      processed_image=None)`, `attach_pair(item_id, *, raw_image, processed_image)`
      (writes `pair_raw.png` and `pair.png`). All rewrite `metadata.json`
      atomically (write a temporary file, then `replace`).
- [x] `load_doodle(item_id) -> dict | None`: the metadata plus `raw` (raw.png if
      present, else processed.png), `processed`, `pair_raw` (or None). None when
      the entry is missing. Validate the id resolves inside `library_root()` the
      way `delete_library_item` does.
- [x] `list_library_items(*, favourites_only=False)`.
- [x] `clear_history_keep_favourites() -> int`: deletes every non-favourite
      entry through `delete_library_item`, returns how many went.
- [x] `save_library_item` writes `favourite: true` explicitly.
- [x] Tests (each must be able to fail for a real bug): same raw bytes twice →
      one entry; a legacy entry without the key is a favourite; favourite
      toggling round-trips; clearing keeps favourites and legacy entries and
      deletes the rest; `load_doodle` returns the pair; `load_doodle("../x")`
      is refused.

## Task 2 — the trail and the browser listener, as pure code

Files: new `colouring_factory/navigation.py`, `colouring_factory/browser_history.py`,
`tests/test_navigation.py`.

- [x] `navigation.py`, no Streamlit import:
      - `DETOURS = frozenset({"generate", "connect"})`; `RESTORABLE = frozenset(
        {"home", "result", "history", "favourites", "characters", "studio"})`.
      - frozen dataclasses `Stop(token, screen, doodle="")` and
        `Trail(stops, position, session, issued)`.
      - `Trail.start(screen, doodle, *, session, token="")`, `.here`,
        `.can_go_back`, `.can_go_forward`, `.back()`, `.forward()`,
        `.go(screen, doodle)` (new token `f"{session}.{issued}"`, `issued + 1`,
        drops stops after the position), `.arrive(params)` (token found → move
        there; unknown → `Trail.start` from `place_from_address(params)` keeping
        that token), `.address()` → `{"screen", "step", "doodle"?}`.
      - `place_from_address(params) -> tuple[str, str]`: unknown screen → home;
        `result` without a doodle → home.
- [x] `browser_history.py`: `LISTENER_JS` (multi-line; binds one `popstate`
      listener on `window`, guarded by a window flag, calling the latest
      `setTriggerValue("moved", window.location.search)`) and
      `step_script(direction, nonce) -> str` returning
      `<script>` that calls `window.history.back()`/`forward()` once per nonce
      (`window.__doodleNavNonce`), mirroring `browser_print.print_trigger_html`.
      The nonce is a string carrying the session, `<session>.<n>`, because the
      tab outlives a session and a bare count restarting at 1 would be ignored.
      Reference implementation proven in Chrome: the throwaway app at
      `/private/tmp/claude-501/-Users-olliepage-Developer-Doodle/c2b0fe80-3472-4e19-abe3-28790859ca3d/scratchpad/nav_spike/app.py`.
- [x] Tests: going somewhere new after stepping back drops the forward stops;
      tokens are never reused, even after going back and forward; `arrive` with a
      known token moves without adding a stop; `arrive` with an unknown token
      starts afresh from the address; `place_from_address` rejects unknown screens
      and a result with no doodle; `step_script` rejects a bad direction.

## Task 3 — record every doodle, and favourites replace the library

Files: `app.py`, `tests/test_app_library.py` (rewritten in place),
`tests/test_ui_conventions.py`.

- [x] State: add `current_doodle_id: ""`, `history_shown: 24`,
      `pending_clear_history: False`; remove `quick_saved`, `library_notice`,
      `library_return` and every read of them.
- [x] Extract `_quick_clean(raw) -> bytes` from `_prepare_quick_outputs` (same
      cached call, same defaults) and use it in both places.
- [x] `_set_current_artwork(raw, *, title, metadata, doodle_id=None)`: when no id
      is given, `record_doodle(...)` with `_quick_clean(raw)`; always set
      `current_doodle_id`.
- [x] `_current_doodle_id()`: records the current picture if a test or restored
      session put `current_raw` in place without an id; used by every favourite
      control.
- [x] `_prepare_pair_outputs`: `attach_pair` to the current entry.
- [x] `_open_doodle(item_id) -> bool`: loads from the store, sets the current
      artwork with the known id, sets `generation_idea` to the concept or title
      (so "Draw this idea again" works — see FB-01 in the characters tests),
      starts a fresh version chain from it, clears candidates, restores the pair
      and prepares both sheets. False when the entry is gone.
- [x] Result screen: the heart toggles favourite ("Add to favourites" /
      "Remove from favourites"); the old saved banner goes.
- [x] Top bar: History, Favourites (n) (disabled with a help line when there are
      none). Homepage corner: History and Favourites (n) once any entry exists.
- [x] Screens `history` and `favourites` replace `library`: shared grid (Open,
      Favourite/Unfavourite, Delete with confirmation that names a favourite);
      History shows `history_shown` tiles with "Show more", and "Clear history,
      keep favourites" with a confirmation.
- [x] Studio: tab "Favourites" with the favourites grid; "Add to favourites"
      writes the name and Studio-cleaned picture via `update_doodle` then
      `set_favourite`.
- [x] Tests (`AppTest`, clicking every route): a drawn picture appears in History
      without pressing anything; tapping an alternative adds it, tapping back
      does not duplicate; the heart adds and removes a favourite; the older
      hand-saved entries show under Favourites; opening from History lands on the
      result screen ready to print with its pair; "Clear history, keep
      favourites" asks, then keeps favourites; Studio's button favourites the
      entry under its new name. `test_saving_is_called_the_same_thing_everywhere`
      asserts "Add to favourites" in both places.

## Task 4 — Back and Forward everywhere, and the browser's buttons

Files: `app.py`, `tests/test_app_smoke.py`, `tests/test_app_characters.py`,
new `tests/test_app_navigation.py`. Escalated to the strategist tier: routing
touches every screen and has invariants (detours, the money guard, the test
runner's page reset) that a mechanical reading would miss.

- [ ] Register the listener each run: `st.components.v2.component(
      "doodle_browser_history", js=LISTENER_JS)`.
- [ ] State: `nav_trail: None`, `nav_script: None`, `nav_nonce: 0`,
      `nav_session`: a short random hex per session.
- [ ] `_sync_navigation()` just before the router: first run → adopt a restorable
      address when the screen is still the default home (reopening a doodle via
      `_open_doodle`), then start the trail; listener reported a move → if on the
      drawing screen, keep what is drawn (as Stop does) and clear the plan, then
      `_show_stop(trail.arrive(params).here)`; finally, when the screen is not a
      detour and its place differs from the trail's stop, `go` and set
      `st.query_params`. Emit any pending `nav_script` once.
- [ ] `_step_back()` / `_step_forward()` as `on_click` callbacks: on a detour,
      Back stops a drawing if there is one and shows the current stop without
      touching the browser; otherwise move the trail, show the stop, queue the
      one-shot script.
- [ ] `_render_nav_arrows(where)`: "Back" and "Forward" buttons with
      `:material/arrow_back:` / `:material/arrow_forward:`, disabled when there
      is nowhere to go. In the top bar, the homepage corner, the drawing screen
      and the connection screen.
- [ ] Remove the characters screen's and connection screen's own Back buttons.
- [ ] Smoke-test fake: a `query_params` dict with `from_dict`, and
      `components.v2.component` returning a mount whose result has `moved=None`.
- [ ] Tests: the arrows start disabled; home → characters → Back → home (replaces
      the old characters Back test); result → History → Back shows the same
      doodle, Forward returns to History; after "New doodle", Back reopens the
      previous doodle from history; a fresh session with
      `?screen=result&doodle=<id>` opens it; Back on the drawing screen with one
      picture drawn keeps it in History and never calls the provider again; the
      Back click queues a script containing `history.back()`.

## Task 5 — docs, verification, ship

- [ ] `docs/ui-conventions.md` Routes and top-bar paragraphs rewritten for
      history, favourites and the arrows; `docs/REFERENCE.md` and README line on
      what is kept locally.
- [ ] Full suite green; run the real app on a spare port and in Chrome check:
      demo drawing recorded, heart, History/Favourites, bar arrows, browser
      Back/Forward, refresh on a result reopening it, Back during a drawing.
- [ ] Retro at `docs/retros/2026-09-12-history-favourites-navigation.md`.
- [ ] `gh pr ready`, review, merge.
