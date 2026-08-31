# Drop a picture — design

Date: 2026-08-31
Branch: `claude/drop-a-picture`, based on `claude/characters` (PR #24, still a draft)
Status: approved for planning

## Problem

Google Search does something small and generous. Drag any image file over the
page and it notices, dims the page, and offers to take it; drop it and the
picture appears inside the search bar as a thumbnail beside whatever you have
typed. No menu, no upload button, no file browser.

Doodle should do the same, because the gesture answers a question Doodle keeps
asking the hard way. A parent has a photograph of a teddy on the desktop and
wants a colouring page of it. Today that means opening Doodle Studio, choosing
"Upload artwork" from a radio, browsing to the file, and accepting a
threshold-and-crop conversion that copies the photograph's edges rather than
drawing the teddy. Or it means saving the teddy as a character first, which is
right when the teddy will recur and heavy-handed when it will not.

The ask, in the requester's words: *when you drag a picture on, it just adds it
to the search bar, and then the user can use the existing configuration to
decide how many pictures to create, what age range to create it for. If you
enter it without any prompt, it will turn it into something that can be coloured
in. If you write it with a prompt, it should use the prompt, and that picture can
be a complement to it.*

## What already exists

- `colouring_factory/browser_print.py` — a pure function returning a `<script>`
  block, handed to `st.html(..., unsafe_allow_javascript=True)` at `app.py:1218`.
  The one place Doodle already runs its own JavaScript, and the house pattern
  for it: a module-level template, a `window.__doodlePrintNonce` guard against
  Streamlit replaying it, elements appended to `document.body`, and a
  unit-testable function that returns a string.
- `colouring_factory/photos.py` — `prepare_photo(raw, max_edge=...)`, the single
  choke-point every uploaded byte passes through. Bakes EXIF rotation into the
  pixels, strips all metadata including GPS and the ICC profile by rebuilding
  the image, flattens transparency onto white, rescales 16-bit greyscale, caps
  the long edge, re-encodes as PNG. Raises `ValueError` for empty, unreadable
  and decompression-bomb input, never crashes. `MAX_PHOTO_EDGE_PX = 1536`,
  `MAX_ARTWORK_EDGE_PX = 6000`. HEIC opens via `pillow_heif.register_heif_opener()`
  at import.
- `colouring_factory/appearance.py` — `describe_appearance(photo, *, provider_id,
  api_key)`, one vision call returning a plain-English sentence about what is in
  a photograph. Refuses Recraft with code `no_text_model`. The characters screen
  fires it the moment a photo is chosen (`app.py:1714-1730`), guarded by a
  sha256 of the bytes so it costs one call per distinct photo, and swallows
  failure to a blank string so the form is never blocked.
- `colouring_factory/generators.py` — `refine_with_provider(...,
  reference_images: Sequence[bytes] = ())`, the only call that carries pictures.
  Enforces the per-provider cap, raises `no_reference_support` when the provider
  takes none, `too_many_references` above the cap, and relabels a content
  refusal carrying a picture as `photo_declined`.
- `colouring_factory/providers.py` — `max_reference_images`: OpenAI 16, Google 4,
  Recraft 0.
- `colouring_factory/prompts.py` — `build_colouring_prompt` (no references),
  `build_character_scene_prompt` (cast references), `build_caricature_prompt`
  (one photograph). `_spliced()` pushes multi-line rule constants to the
  template's margin. Rule order is enforced by tests: overrides go after the
  four profile lines, because stated first they were ignored.
- `app.py:1022` `_render_home_options` — the settings line under the prompt bar:
  how many pictures, who it is for, drawing style, and the cast popover.
- `app.py:2371` `_build_generation_plan` — freezes a batch: briefs, levels,
  prompts, `generation_references`, `generation_uses_cast`. `app.py:2490`
  `_draw_next_quick_picture` draws one job per script run.
- `colouring_factory/timings.py` — `settings_key(..., with_references)` partitions
  the waiting-screen histogram, because a drawing carrying pictures is slower.
- The only two `st.file_uploader` calls are `app.py:1706` (characters screen,
  accepts HEIC) and `app.py:3805` (Studio "Upload artwork", does not). Both sit
  behind `st.stop()` on screens the homepage never renders. **There is no
  uploader on the homepage.**

## Evidence

Every browser mechanic below was proved on 2026-08-31 against the installed
Streamlit 1.62.0 in headless Chrome 151, driven over the Chrome DevTools
Protocol. Probe app and harness are preserved in the session scratchpad under
`scratchpad/probe2/`. Nothing was assumed from documentation.

**Streamlit 1.62 has no iframes.** `document.querySelectorAll("iframe").length`
returned 0 on a running app. `st.html(..., unsafe_allow_javascript=True)`
executes in the top-level document — the compiled frontend sanitises with
DOMPurify configured `ADD_TAGS:['script','style']`, assigns to `innerHTML`, then
replaces each `<script>` with a freshly created one so it runs. A window-level
drag listener therefore covers the whole page. The deprecated
`st.components.v1.html` genuinely is a sandboxed iframe and is not a candidate.

**A component cannot carry the bytes.** `st.components.v2` exists and is also
not iframed (it mounts in an open shadow root; `BidiComponent.Bbe1415k.js` calls
`attachShadow({mode:'open'})` and contains no iframe). But its return path is
widget state over the websocket, and `server.maxWidgetStateSize` caps that at
25 MB with an error naming custom components. `.streamlit/config.toml:16` sets
`maxUploadSize = 200` with a comment recording that a phone photograph is often
over 30 MB. A component round-trip would break the exact case that config exists
for. Forwarding into a real `st.file_uploader` instead sends the bytes over
`/_stcore/upload_file`, where the 200 MB limit applies.

**A hidden uploader still receives an injected file.** With the uploader inside
`st.container(key="doodle-drop-well")` — which renders `class="... st-key-doodle-drop-well ..."` —
hidden by CSS, a drop dispatched on the page `<h1>` reached Python. Both
`display:none` and the visually-hidden `clip-path:inset(50%)` pattern worked.
`display:none` is chosen: the clip-path version leaves a 16×1 pixel box behind,
because Streamlit's own vertical-block rule sets `min-width:16px` and beats a
declared `width:1px`.

**The uploader must live outside the form.** Outside `st.form("home_prompt_form")`,
a drop fired its own rerun in about 400 ms with the form still reporting
`submitted=False`. Inside the form, the file was staged in the browser and
Python saw nothing across 8000 ms of polling; it arrived only when "Draw it" was
pressed. The typed idea survives the drop either way — after the drop-triggered
rerun the text input still held `a dragon in a teacup`.

**A rejected drop is completely silent.** This is the hazard the design has to
answer. Streamlit's client-side refusals — `Error: image/bmp files are not
allowed.`, `Error: File must be 200.0MB or smaller.` — are rendered as text
*inside the uploader's own block*, which is the block being hidden, and no rerun
fires. Python is never told. The drop handler must therefore check the extension
and the size itself, in JavaScript, before injecting.

**The type filter reads the filename extension and ignores the MIME type.**
`photo.png` carrying MIME `image/bmp` was accepted; a file named `screenshot`
carrying a valid `image/png` MIME was refused. The error text quotes the MIME,
which is not what the check reads. `IMG_4021.HEIC` (the exact form an iPhone
hands over, uppercase) passed; `no-mime.heic` with an empty MIME passed;
`live.heif` was refused, so `heif` must join the list.

**Thirty megabytes is a non-event.** A 31,457,280-byte drop reached Python whole
in 518 ms as a single `PUT` to `/_stcore/upload_file/<session>/<file>` returning
204, initiated by XHR. The websocket carried only control frames over the same
window, the largest 740 characters. Above the ceiling it fails silently: a 201 MB
drop produced no rerun and no message anywhere the user could see.

**The guard matters, and only under one condition.** With a byte-identical
`st.html` payload Streamlit never re-inserts the script — after three reruns,
`{overlays:1, scriptExecutions:1}`. The moment anything in the payload varies,
the block remounts and the script replays: without a guard that produced
`{overlays:4, listenerAdds:12}` and one user drop handled four times. With a
`window.__doodleDrop` boolean guard under the same varying payload,
`{overlays:1, listenerAdds:3}` and one handler call per drop. So the payload
stays static *and* the guard stays, defending different things. The
`browser_print.py` nonce habit is deliberately not copied: printing wants to
re-fire, this does not.

**The overlay must be appended to `document.body`.** That is what makes it
outlive Streamlit redrawing its tree; an overlay written into the `st.html`
markup is destroyed on remount. `st.html` clears its own div on unmount, so the
overlay is ours to remove and nothing will clean it up.

## Goals

1. Drag a picture anywhere over Doodle and drop it, with no prior gesture.
2. The dropped picture appears in the prompt bar and rides the settings already
   on the homepage — how many, who it is for, which style, who else is in it.
3. With no words typed, Doodle draws that picture as a colouring page.
4. With words typed, the picture is the thing to draw and the words are the
   scene.
5. Nothing about the homepage's shape changes when there is no picture attached.

## Non-goals

- Several pictures at once. Both existing uploaders are single-file, and the
  whole downstream pipeline holds one `current_raw`.
- Content-based routing (deciding from the pixels whether this is a photograph
  to redraw or a scan to trace). The free local trace already exists in Doodle
  Studio and stays there.
- Saving a dropped picture as a character. A dropped picture is a one-off; the
  characters screen is where a recurring one belongs. An "add to your characters"
  route from the result screen is a later feature, not this one.
- Drag-to-reorder, drag out, or dropping a URL rather than a file.

## Design

### A dropped picture is a character you never saved

This is the decision everything else follows from, and it was chosen against two
alternatives. The picture supplies identity; the words supply the scene. Drop a
photograph of a teddy and type *riding a rocket to the moon*, and the drawing is
that teddy — bald ear, mismatched button eye — in a rocket. The rejected
alternatives were leaving the role unstated (flexible for landscapes, wobbly on
the common case) and inverting it so the picture supplies style and setting
(which would draw a generic teddy when the parent meant theirs).

It also means the feature reuses the machinery the characters work already
proved, rather than building a parallel path.

### The overlay

New module `colouring_factory/browser_drop.py`, sibling to `browser_print.py` and
following it exactly: a module-level constant, one pure function returning a
string, no interpolation of anything user-supplied.

```python
def drop_overlay_html(*, accepted: Sequence[str], max_bytes: int) -> str: ...
```

The two arguments are Doodle's own module-level constants, never user text, and
both are serialised as a JSON array of extensions and an integer. Keeping the
payload byte-identical across reruns is a requirement, not a nicety, so neither
argument may vary with session state — and the script is therefore blind to which
screen it is on, which provider is connected, and what has been typed. Everything
conditional is decided in Python.

The panel carries one line, *Drop a picture to draw with*, over a dashed border
in Doodle's own colours.

The script:

- guards on `window.__doodleDrop`, returning early if already wired;
- appends one `<div id="doodle-drop-overlay">` to `document.body`;
- listens on `window` for `dragenter`, `dragover`, `dragleave` and `drop`, all
  with `capture`, calling `preventDefault()` on `dragenter` and `dragover` so the
  browser does not navigate away to the file;
- counts `dragenter` against `dragleave` so crossing a child boundary does not
  flicker the panel;
- ignores drags carrying no file (`dataTransfer.types` without `Files`), so
  dragging selected text does not raise the panel;
- on drop, takes the first file, lowercases its name, and checks the extension
  against `accepted` and its size against `max_bytes` **before** injecting —
  because Streamlit's own refusal would be invisible;
- on a good file, resolves the input lazily at drop time with
  `document.querySelector('.st-key-doodle-drop-well [data-testid="stFileUploaderDropzoneInput"]')`,
  then `const dt = new DataTransfer(); dt.items.add(file); input.files = dt.files;
  input.dispatchEvent(new Event("change", {bubbles: true}))`;
- on a bad file, shows *Doodle can draw from a photo, not that kind of file* (or
  the size equivalent) in the overlay for a moment and injects nothing;
- when the input is not found — because this screen has no drop well — shows
  *There is nowhere for a picture to go on this screen* and injects nothing.

Resolving the input at drop time rather than at setup time is essential: the
script runs before elements declared later in the script body have rendered.

`data-testid="stFileUploaderDropzoneInput"` is the one Streamlit-internal
contract this feature depends on. It carries a comment naming the version it was
verified against, and the handler fails soft if it moves.

### The drop well

A new third `st.file_uploader`, rendered on every screen that has somewhere for a
picture to go, inside `st.container(key="doodle-drop-well")` which a CSS rule sets
to `display:none`.

```python
st.file_uploader(
    "Drop a picture",
    type=["png", "jpg", "jpeg", "webp", "heic", "heif"],
    accept_multiple_files=False,
    key=f"drop_well_{st.session_state.drop_well_nonce}",
    label_visibility="collapsed",
)
```

`heif` joins the list on the evidence above. The key carries a nonce so the
widget can be emptied by bumping an integer rather than by assigning to a widget
key from the script body, which Streamlit refuses once the widget exists — the
mistake that shipped a crashing recovery button on 2026-08-30.

On the homepage the well is placed **outside** `st.form("home_prompt_form")`,
immediately after it.

### Adoption

When the well holds a file whose sha256 differs from `dropped_picture_hash`:

1. `prepare_photo(raw)` at the default `MAX_PHOTO_EDGE_PX = 1536`. The picture is
   going to a model as a reference, not to a printer, so the 6000-pixel artwork
   cap does not apply. `ValueError` becomes an `st.error` and nothing is stored.
2. Store the prepared bytes in `dropped_picture` and the hash in
   `dropped_picture_hash`.
3. `describe_appearance(prepared, ...)` on the connected provider, failing soft
   to `""` exactly as the characters screen does, stored in
   `dropped_picture_appearance`.
4. Set `quick_mode = "ai"`, because a drop made while demo mode is active would
   otherwise be silently discarded.
5. `st.rerun()`.

No paid drawing happens on drop. The description is one cheap call on the
provider's text model (`gpt-5-mini`, `gemini-3.5-flash-lite`), and it earns its
place twice: it is what the generating screen shows when no words were typed, and
it is what `build_variation_briefs` reads to pull several drawings apart.

New session keys, all declared in `_initialise_state`'s defaults dict and all
cleared in `_start_new_doodle`: `dropped_picture`, `dropped_picture_hash`,
`dropped_picture_appearance`, `dropped_picture_name`, `drop_well_nonce`.

### The prompt bar

Inside the form, before the text input, a keyed container holds
`st.image(thumbnail, width=32)` when a picture is attached, positioned by CSS
over the left inset of the 62-pixel pill with matching left padding on the input
itself. The thumbnail is a small square crop derived from the prepared bytes and
cached with `@st.cache_data` on their hash, the same way `_character_portrait`
caches a character's thumbnail, rather than shipping a 1536-pixel PNG to be drawn
at 32. Using `st.image` rather than a CSS `background-image` keeps the picture's
bytes out of the injected stylesheet entirely.

The clear control is a second `st.form_submit_button`, tertiary, labelled
`Remove picture` with `icon=":material/close:"`, positioned over the pill's right
end. It renders only when a picture is attached, so
`tests/test_app_circle_guidance.py:104` — which asserts the homepage's buttons are
exactly `["Draw it", "Add a character"]` — still passes on a homepage with no
picture, and gains a case for one with.

Nothing here changes the homepage's height or adds an element below the bar, which
is what `docs/ui-conventions.md:110-116` requires.

The placeholder changes from *What shall we draw?* to *What shall we draw with it?*
while a picture is attached.

### Drawing with it

`_submit_home_prompt` currently returns immediately on a blank prompt, and two
tests in `tests/test_homepage.py` pin that. It gains one condition: a blank prompt
with a picture attached proceeds, using the picture's description as the idea, or
the fallback string `the picture you dropped` when the description call failed.
A blank prompt with no picture still does nothing.

That synthesised idea is what the generating screen renders as the largest words
on the page, and what the connect screen's "your idea is waiting" card shows, so
a parent who drops a picture before connecting a key can see their picture is
still held.

`_build_generation_plan` changes in three places:

- `references` becomes the cast portraits **plus** the dropped picture, in that
  order, so the ordinal words in the prompt keep matching the attachment order.
- The prompt builder is `build_character_scene_prompt` whenever there is a cast
  *or* a dropped picture. With neither, `build_colouring_prompt` as today.
- `generation_uses_cast` becomes `generation_uses_references`, true when either
  is present, so `_draw_next_quick_picture` routes to `refine_with_provider` and
  `record_timing`'s `with_references` flag files the drawing in the right bucket.
  Six occurrences in `app.py` and none in the tests: the default at `app.py:378`,
  the reset at `2363`, the write at `2470`, the routing branch at `2500`, the
  timing record at `2539`, and the waiting screen's own estimate at `3086`. That
  last one matters as much as the others — a drawing carrying a picture is slower,
  and filing it under "words" trains the wrong distribution on the screen the
  parent watches while waiting.

When the idea was synthesised from the description, `build_variation_briefs` runs
on it as normal, so four pictures are four readings of the dropped picture rather
than four copies.

### The prompt itself

`build_character_scene_prompt` learns that a reference has a source. Its character
tuples gain a `source` of `portrait` or `dropped`, and two things branch on it:

- The introduction sentence. Today: *The first picture is Doodle's drawing of
  {name}, a {article}.* That is a lie about a photograph, so a dropped picture
  gets its own sentence naming it as a picture the parent supplied and instructing
  that what is in it is what to draw.
- `PORTRAIT_MATCH_RULE`, which asserts the reference is *the line drawing Doodle
  has already made*, gains a twin, `DROPPED_PICTURE_RULE`, spliced through
  `_spliced()` so the ragged-margin tests stay green, and placed after the four
  profile lines so it is read as an override.

A dropped picture has no name and no marks sentence, so the introduction loop
must tolerate both being empty. `CHARACTER_LIKENESS_RULE` already says *the
attached pictures are the reference for how these characters really look*, which
is true of a photograph, and needs no change.

One builder, one ordering, one set of ordering tests. A parallel builder was
rejected because it would duplicate the rule ordering that four separate tests
guard.

### Reference slots

A dropped picture occupies one of the provider's reference slots. While one is
attached, the cast popover's cap becomes `max_reference_images - 1` — three on
Gemini rather than four — and its caption says why. This honours the house rule
that the interface never renders a control that can only fail, rather than letting
`refine_with_provider` raise `too_many_references` in the middle of a paid batch.

### Recraft

Recraft's `max_reference_images` is 0 and it has no text model, so it can draw
from neither the picture nor a description of it. The drop well is still rendered
and the picture is still accepted, and Python then refuses it at adoption with the
existing guidance code `no_reference_support`, which names the control that fixes
it. Refusing in JavaScript instead would mean either varying the payload by
provider, which breaks the byte-identical rule, or showing the generic
nowhere-to-go message, which explains nothing. A wasted upload of a local file
costs nothing; a parent who cannot tell why their picture vanished costs a lot.

### Where it works

The overlay arms on every screen, because a window listener that does not call
`preventDefault()` lets the browser navigate away to the dropped file, and losing
the app is worse than any message. The drop well — and therefore a destination —
is rendered on three screens: the homepage, the characters screen and Doodle
Studio. On the characters screen a drop fills the existing "Add a picture"
uploader; in Studio it fills "Upload artwork" and switches the "Artwork source"
radio to match. On the connect, generating, result and library screens there is no
well, so the overlay says the picture has nowhere to go here and nothing is
uploaded.

### Cost

A dropped picture buys no extra drawings. Four pictures is four paid calls exactly
as it is today, each one now carrying the photograph. One cheap description call
happens at drop time. The homepage help text under "how many" says *each one is
drawn separately, from its own reading of your idea, and costs one generation*,
and gains a clause about the picture riding along.

### Privacy copy

The About tab's privacy paragraph (`app.py:4358-4375`) gains a sentence: a dropped
picture is sent to the connected service, once to describe it and again with each
drawing in the batch, and is not kept on this computer unless the doodle is saved.
Six tests in `tests/test_app_privacy.py` guard that paragraph and gain a case.

That paragraph currently states that a saved character's *likeness always comes
from the photograph rather than from the drawn portrait*. Commit `2a74542`
reversed that — `app.py:2427-2429` loads `portrait=True` — and the stacked comment
block at `app.py:2417-2430` contains both decisions, contradicting itself. The
caption at `app.py:1693-1703` repeats the stale claim. Correcting all three is in
scope for this branch, because the feature edits the same paragraph and shipping a
new sentence beside a false one is worse than fixing both.

## Error handling

Every failure has an existing guidance code, so `tests/test_guidance.py` — which
greps every module for `code="..."` and fails on the first orphan — needs no new
entries:

| Failure | Where | What the parent sees |
|---|---|---|
| Wrong file type, or over 200 MB | JavaScript, before injection | The overlay says so; nothing is uploaded |
| Dropped on a screen with no well | JavaScript, input not found | The overlay says there is nowhere for it to go |
| Unreadable image, decompression bomb | `prepare_photo` raises `ValueError` | `st.error` with the message; no picture attached |
| Provider takes no references (Recraft) | Python, at adoption | `no_reference_support` |
| Cast plus picture over the cap | Cast popover disables further ticks | Prevented, not reported |
| Description call fails | Swallowed to `""` | Nothing; the fallback idea is used |
| Provider refuses the picture | `refine_with_provider` | `photo_declined` |

## Testing

Python behaviour goes through `AppTest` driving the real `app.py`, because a
hand-written fake Streamlit cannot tell a rendered panel from a missing one.
Following `tests/test_app_characters.py`, provider functions are monkeypatched at
the module the import pulls from, never on `app`, since `AppTest` re-executes the
whole module body on every run.

- Setting the drop well's value with a `(name, bytes, mime)` tuple attaches the
  picture: `dropped_picture` is non-empty, EXIF and GPS are gone from it, and the
  original filename is not in any stored metadata.
- With no words typed, clicking "Draw it" reaches `refine_with_provider` with the
  dropped bytes in `reference_images`, and the prompt contains the dropped-picture
  rule and not the "Doodle's drawing of" sentence.
- With words typed, the prompt contains both the words and the rule, and the
  words survive the drop-triggered rerun.
- "Remove picture" is clicked, not merely asserted present, and the picture is
  gone afterwards with no exception raised.
- A cast plus a dropped picture sends both, in attachment order matching the
  ordinal words.
- On Gemini with four characters ticked, attaching a picture reduces the cap and
  no plan is built that exceeds it.
- `record_timing` receives `with_references=True` for a drawing carrying only a
  dropped picture.
- `_start_new_doodle` clears every new key.
- An unreadable drop produces `at.error`, no `at.exception`, and no attached
  picture.

`drop_overlay_html` is unit-tested as a pure function: the guard name is present,
the accepted extensions and the byte ceiling appear, the payload is byte-identical
across two calls with the same arguments, and no user-supplied string can reach it.

`AppTest` has no DOM and cannot exercise the browser layer. The Chrome DevTools
proof is re-run against the real app before the branch is called done, and the
harness is kept in the scratchpad rather than committed.

## Judgement calls

**One cheap vision call on drop.** It adds a call to a gesture that should feel
instant. It is included because a two-tone line drawing discards colour and tone,
words are the surviving channel for them, and the characters work already
established this. It also gives the generating screen something to show and the
variation planner something to work with, both of which would otherwise be blank
for an image-only drop.

**Stacked on `claude/characters` rather than branched from `main`.** The feature
uses `refine_with_provider`'s `reference_images`, `describe_appearance`,
`prepare_photo` and `build_character_scene_prompt`, none of which are in `main`.
Branching from `main` would mean reimplementing them. The dependency is recorded
here; this branch merges after #24.

**No consent step, no delete-after-use.** Doodle is a local app with one user
drawing for his own children. A picture in `~/.doodle` is no more exposed than
the same picture in Downloads.
