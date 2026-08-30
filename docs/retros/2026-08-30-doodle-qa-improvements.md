# Retro: the Doodle QA pass

Date: 2026-08-30
Pull request: [#4](https://github.com/OlliePage/Doodle/pull/4), merged into `main` as `00194b9`
Tests: 23 before, 127 after

## What was asked for

Five problems from real use: no way to discover how to add an API key and no provider
other than OpenAI; warnings that name a problem without a route to the fix; a colliding
icon in the homepage search bar; variations of one idea coming out near-identical; and no
way to see where a badge's boundaries fall or to keep artwork inside them.

## What the code actually said

Four of the five had a cause that was visible on a first read, and one had a cause that
was not.

The key was read from an environment variable or a sidebar password box, and the sidebar
starts collapsed, so a new user never saw it. `save_settings` only ever persisted printer
calibration, so the key had to be retyped every launch.

The variations were identical because `generators.py` sent every variant the same prompt
with one sentence appended asking the model to vary the pose. An image model given a
near-identical prompt returns a near-identical picture.

The badge artwork was scaled to fill the *square* bounding the safe circle and then
clipped to the circle, so all four corners of every picture were discarded. Nothing
reported this.

The search bar collision was Streamlit's own `InputInstructions` hint and clear button,
both right-aligned inside an input the homepage CSS had shrunk to a 62-pixel pill.

The one that was not visible: a whole first-run experience, roughly 90 lines including a
"Your first Doodle is ready" screen, could never run. Its flag was initialised to `False`
and nothing anywhere set it to `True`.

## What went well

**Reading the code before theorising paid off immediately.** Every one of the five causes
was found by opening the file rather than by reasoning about symptoms, and the fifth
problem was found by reading code nobody had asked about.

**Verifying the provider API against live documentation, rather than memory.** The
training data named Gemini image models that were several generations old and an endpoint
that no longer exists. Building on remembered names would have produced code that failed
at the first real call, in a way that looks like a key problem rather than a wrong URL.

**Checking arithmetic against the real function instead of reasoning about it.** The
one-click margin fix rests on a calculation; running it through
`compute_circle_sheet_plan` showed a 95 mm badge at a 60 mm margin holds zero circles and
the computed 57.5 mm suggestion holds one. An earlier version of that test asserted
something impossible, because the config it built already fitted.

## What went badly

**The unit tests were green while a whole panel never rendered.** The guidance for a
badge sheet that holds nothing was wired to the exception path, but
`compute_circle_sheet_plan` returns a zero-capacity plan rather than raising. The most
likely failure in practice showed "0 circles fit" with no explanation and no way forward.
The tests exercised the margin calculation and the guidance map separately and never the
wiring between them, so they could not catch it. Only running the app did.

The lesson is specific rather than general: this repo's `test_app_smoke.py` drives a
hand-written fake Streamlit whose `__getattr__` returns a no-op for any command it does
not implement, so a missing panel is indistinguishable from a rendered one. Streamlit
ships `AppTest`, which runs the real script against the real runtime and can be asked what
each element contains. Anything asserting what the user sees belongs there.

**Two tests were rewritten that should never have existed in that form.** Both asserted on
internal names — a state key called `studio_open`, and the literal string
`_doodle_logo("hero")` — and broke on a rename without a bug existing. They now assert
what a user would notice.

**A stale branch was noticed late.** Three of Ollie's own pull requests landed on `main`
during the session. Checking `origin/main` before opening the PR, rather than after
GitHub reported a conflict, would have been cheaper.

## Things found while merging

Pull request #2 raised the black-and-white threshold so pale strokes survive as solid
lines, changing the dataclass default and the studio slider. The first-run path still had
the old number written out as a literal, so the very first picture a new user sees was
processed at the old threshold and still came out with broken outlines. That path now
reads `ProcessingOptions`, and a test fails if the number is copied back in.

## Two environment frictions worth fixing

`GITHUB_TOKEN` is exported in the shell and silently overrides the GitHub CLI's active
account, so `gh` authenticates as `milo-garth` and cannot see `OlliePage/Doodle`. `git
push` is unaffected, because git uses the keychain instead, which makes the failure look
like a repository permissions problem. `gh auth switch` refuses outright while the
variable is set. Finding what exports it would remove a recurring workaround.

A formatter hook removes imports that are unused at the moment of an edit. Adding an
import in one edit and its first use in the next means the import is gone by the time the
second edit lands. This happened four times, each costing a failing test run, and the
resulting error points at the call site rather than at the missing import.

## Decisions worth remembering

Inscribing artwork inside the safe circle makes it about 71 per cent of the safe diameter,
because a square that fits inside a circle is narrower than the circle. That is a visible
reduction, accepted deliberately so that nothing is cut off, with the previous behaviour
kept as an explicit "Fill the circle" choice rather than removed.

The badge preview is produced by exporting a real single-badge PDF through the same code
path as the printed sheet and rasterising it. A preview drawn independently would be free
to drift from what prints, which is the one thing a print-geometry tool must not do.

Variation briefs fall back to curated axes on any provider failure rather than
propagating, because a weaker variation beats no picture at all.
