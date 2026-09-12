# History, favourites, and Back and Forward that work — design

Approved in conversation on 2026-09-12.

## What was asked for

Every doodle is kept in a **history** automatically, and a **favourites** list
replaces today's "Saved doodles" library. Every screen carries a **Back** and a
**Forward** button at the top, and the browser's own Back and Forward buttons
(and the trackpad swipe) finally move around the app instead of doing nothing.

## Decisions taken

- **What goes into history:** every picture that appears on screen as the
  current doodle — a new drawing, an alternative tapped to use instead, each
  change made to it, anything set in Doodle Studio (generated, uploaded or a
  demo), and a character's portrait opened as a doodle. Alternatives that were
  drawn but never tapped are not kept. The same picture appearing again (tapping
  back to an alternative, reopening from history) reuses its entry.
- **Navigation reach:** the app's bar *and* the browser's buttons, through one
  shared trail.
- **Retention:** history is never trimmed automatically. Each entry can be
  deleted, and History offers "Clear history, keep favourites". At about 1.5 MB
  a picture (measured: 11 saved doodles, 16 MB), twenty a week is ~1.5 GB a year.

## Storage

The existing store, `~/.doodle/library/<id>/` (`processed.png`, `raw.png`,
`metadata.json`), becomes the single store for both lists. Nothing is copied or
moved.

- `metadata.json` gains `favourite` (bool) and `raw_sha256` (hex digest of
  `raw.png`, used to recognise the same picture again).
- An entry with no `favourite` key was saved by hand before history existed, so
  it counts as a favourite. New automatic entries are written with
  `favourite: false`.
- A doodle drawn as a pair keeps its grown-up sheet in the same entry
  (`pair_raw.png`, `pair.png`), so reopening brings both sheets back.

Naming note: `colouring_factory/history.py` already exists and is the in-session
chain of *versions* behind "Go back to this". It is unrelated and keeps its
name; the new store functions live in `colouring_factory/storage.py`.

## When a doodle is recorded

`_set_current_artwork` in `app.py` is the one function every route above passes
through. It records the picture (quick-cleaned the same way the result screen
cleans it, which is cached, so no extra work) and remembers the entry's id as
`current_doodle_id`. Reopening an entry passes its id straight in, so reopening
never writes a duplicate — including the 11 older entries, which have no stored
digest. `_prepare_pair_outputs` attaches the grown-up sheet to the current entry.

## What the parent sees

- **One bar at the top of every screen:** Back, Forward, the Doodle wordmark
  (goes home), History, Favourites (n), New doodle. The homepage keeps its bare
  shape: Back and Forward sit small in its top-left corner and History and
  Favourites in its top-right, the latter two only once any doodle exists. The
  drawing screen and the connection screen carry the arrows too.
- **Result screen:** "Save to your doodles" becomes a heart that switches the
  doodle in and out of favourites ("Add to favourites" / "Remove from
  favourites").
- **History and Favourites screens:** today's grid, newest first, each tile with
  Open, a heart and Delete. Deleting asks first (and says so when the entry is a
  favourite). History shows the latest 24 with "Show more". History also offers
  "Clear history, keep favourites", which asks first.
- **Doodle Studio:** the "Saved doodles" tab becomes "Favourites"; its save
  button becomes "Add to favourites", keeping the name box and writing the
  Studio-cleaned picture and that name into the entry.
- The scattered in-page Back buttons (characters screen, connection screen, the
  old library screen) go; the bar's Back replaces them.

## Navigation

Proven on 2026-09-12 in a throwaway app against Streamlit 1.62/1.63, in both
the test runner and a real Chrome. The findings shaped the design:

- Streamlit's multipage switch writes **two** browser-history entries per move
  (the first a junk address), so Back would need pressing twice. Not used.
- Changing only the address's parameters (`st.query_params`) writes **one**
  entry per move. Used.
- When the browser's Back changes only the parameters, Streamlit redraws
  nothing. A small invisible custom component (CCv2, `st.components.v2`)
  listens for the browser's `popstate` and reports the restored address to
  Python as a trigger value. Its script lives as a string in
  `colouring_factory/browser_history.py`; `app.py` registers it each run, which
  Streamlit accepts silently because the definition is identical.
- Streamlit skips an address update identical to the last one it sent, so every
  stop is stamped with a never-reused step token, `<session>.<n>`.
- The test runner resets the page between runs but keeps the parameters, so
  Python never infers movement from the address on its own; only the listener's
  report counts as the browser moving.

Model (pure logic, `colouring_factory/navigation.py`): a **trail** of stops, each
`(token, screen, doodle)`, and a position. The address is
`?screen=<screen>&doodle=<id>&step=<token>`.

- *The app moves* (any code sets `screen`, or the current doodle changes on the
  result screen): if the new place differs from the trail's current stop, a new
  stop is added (anything forward of the position is dropped, as in a browser)
  and `st.query_params` is set to its address.
- *The browser moves:* the listener reports the new address; its token is looked
  up in the trail and the app shows that stop — reopening the doodle from
  history when it is not the one on screen. An unknown token (a tab refreshed
  earlier) starts a fresh trail from the address.
- *The bar's arrows* move the trail first (so the screen changes at once, and
  the test runner sees it), then emit a one-shot script calling
  `history.back()`/`history.forward()`. When the browser's report arrives it
  names the stop already shown, so nothing further happens.
- *Detours are not stops:* the drawing screen and the connection screen never get
  an address. No Back or Forward can land on the drawing screen and pay for a
  picture again. Back on the drawing screen, the bar's or the browser's, is
  exactly Stop: with pictures already drawn it lands on the result screen with
  them (they were paid for), and with none it returns to the stop the drawing
  was asked from. The bar's Back on the connection screen returns to the stop
  it was reached from. (Revised after review on 2026-09-12: Back first walked
  away from pictures already drawn, keeping only the first in History.)
- *A stop that can no longer be shown* (its doodle deleted since) is rewritten
  in place to the homepage, keeping its token, so the stops around it survive.
- *Deleting the doodle on screen* also forgets it from memory, so nothing can
  record it again.
- *A fresh page load* (refresh, bookmark) with `screen=result&doodle=<id>` reopens
  that doodle from history; any other known screen opens that screen; anything
  unknown opens the homepage.

## Testing

- Unit tests for the store and for the trail logic.
- `AppTest` click-through for every visible route: recording, favouriting,
  History/Favourites screens, the arrows, Back reopening a doodle after "New
  doodle", a fresh load reopening from the address, Back during a drawing.
- One autouse fixture points every test at a temporary data folder, so recording
  can never write into the real `~/.doodle`.
- The real app in Chrome for the browser's own buttons, after the suite is green.
