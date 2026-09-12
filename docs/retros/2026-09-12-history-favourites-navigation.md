# History, favourites and Back and Forward — retro, 2026-09-12

Asked for: every doodle kept in a history automatically, favourites in place
of the saved-doodles library, and Back and Forward at the top of every screen
that the browser's own buttons agree with.

## What shaped the build

- **The obvious mechanism was wrong, and a throwaway app found out cheaply.**
  Streamlit's own pages looked like the answer, but each move there writes two
  browser-history entries (the first a junk address), so the browser's Back
  would have needed pressing twice. Changing only the address's parameters
  writes one; the browser's Back then changes the address without Streamlit
  redrawing anything, which a small listener component fixes. Twenty minutes in
  a scratch app in Chrome saved building the wrong version into a 5,000-line
  `app.py`.
- **The test runner and the browser disagree about pages.** The runner resets
  to the default page between runs but keeps the parameters. Hence the rule
  that only the listener's report counts as the browser moving, and hence the
  never-reused step token on every stop.
- **Detours, not stops.** The drawing screen spends money the moment it is
  shown, so it never gets an address and Back on it counts as Stop. The
  connection screen was made a detour too, so Back from it returns to where it
  was reached from without a special return key.
- **Back to the homepage used to bounce to Studio.** An old rule sent the
  homepage to Studio whenever a doodle was in memory. It now applies only on a
  session's first run.

## What went wrong

- A delete of the doodle on screen left the app holding the id of an entry
  that had gone; the heart then crashed writing to it. Caught in review, fixed
  by re-recording a picture whose entry has disappeared.
- A test-and-commit command piped pytest into `tail`, so the commit was gated
  on `tail`'s exit status; and `addopts = "-q"` plus another `-q` hides the
  summary line. Nothing broken was committed, but the verdict was unchecked
  until re-run. Now in memory as "pytest quiet hides the verdict".
- A recursive force-delete of a half-built environment was refused by Ollie.
  Reuse or rename instead; never `rm -rf`.
- The History and Favourites step took 33 minutes of worker time against an
  estimate of 15 to 20, mostly in adjusting tests that clicked the first button
  on a screen; putting Back and Forward first broke three more such tests later.
  Tests should find buttons by label.
