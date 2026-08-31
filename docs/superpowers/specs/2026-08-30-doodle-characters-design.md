# Your characters — design

Date: 2026-08-30
Branch: `claude/characters`
Status: approved for planning

## Problem

Doodle draws whatever you describe, but it cannot draw *your* people. Ask for a
girl walking in a forest and you get a girl; you cannot get your daughter. The
whole appeal of a colouring page for a small child is seeing herself in it,
colouring in her own hair and her own glasses, standing next to a lion or a
teddy she recognises.

Two requests, which this design treats as one feature:

1. Upload a picture of someone and have that person be the subject of a
   generated scene.
2. Upload a picture and get a cartoon of it, the way a street artist draws
   people, exaggerating what is distinctive.

## What already exists

- `colouring_factory/generators.py` — `refine_with_provider(...)` takes one
  picture plus a prompt and returns a new picture, on all three providers.
  Nothing takes more than one input picture.
- `colouring_factory/providers.py` — a frozen `ProviderSpec` registry where
  capability is data (`supports_edit`, `supports_seed`, `edit_closeness`), never
  a branch on a provider's name. The comment at `providers.py:22-24` records the
  bug that taught this.
- `colouring_factory/prompts.py` — `build_colouring_prompt`, four `DETAIL_LEVELS`
  (2-3 years, 4-5 years, 6-9 years, Grown-up), four `STYLE_PRESETS` including
  "Badge portrait", and `TARGET_RULES` including "Round badge".
- `colouring_factory/storage.py` — `data_root()`, `library_root()`,
  `save_library_item`, settings read and written atomically.
- `colouring_factory/image_processing.py` — `normalise_line_art` turning
  arbitrary artwork into clean binary line art.
- `colouring_factory/badge_preview.py` — `render_badge_preview` producing a badge
  PNG by exporting a real single-badge PDF, so preview cannot drift from print.
- `app.py` — a `screen` state machine, the homepage with three settings popovers
  on a grey line, and the result screen which since #23 renders a second sheet
  beneath the first (`_render_grown_up_sheet`).
- The only `st.file_uploader` is Doodle Studio's "Upload artwork" source, for
  existing line art. It is not an input to a model.

## Goals

1. Save a character once — a person, a toy or a character — and put it in any
   drawing afterwards.
2. Draw a person recognisably, without making the page too fiddly for the child
   it is for.
3. Support several characters in one picture.
4. Make a caricature of a saved character, printable through everything Doodle
   already builds, including badges.
5. Keep every new picture inside the existing artwork lifecycle, so the studio,
   the circle sheet, the badge preview and custom page sizes apply without
   further work.

## Non-goals

- Choosing where in a scene a character stands. Words do that well enough.
- Any face recognition, or checking that two pictures are the same person.
  Doodle never inspects a photograph itself.
- Sharing a cast between machines.
- A consent step or age gate. Doodle is a local app with one user drawing for
  his own children; see "Judgement calls" below.
- Making Recraft work. Its `imageToImage` endpoint takes one picture per request
  through a multipart field, so it cannot carry a cast. It keeps everything it
  does today.

## Evidence

Eleven test generations against OpenAI on 2026-08-30 settled four questions that
could not be answered by reading code. No photograph of a real person was used;
every reference was invented for the test. Images and prompts are preserved in
the session scratchpad.

**Several references work.** `client.images.edit` types `image` as
`Union[FileTypes, SequenceNotStr[FileTypes]]` and documents up to 16 pictures for
the GPT image models including `gpt-image-2`, Doodle's default
(`openai/types/image_edit_params.py:15-25`). A two-element list was confirmed on
the wire as two `image[]` multipart parts. Two invented photographs produced one
colouring page containing both people, with every distinguishing feature carried
through including clothing.

**The detail dial has to be split.** `DETAIL_LEVELS` moves two things at once:
how fine the line work is, and how large the colouring regions are. At "2-3
years" a face comes back as a generic cartoon child wearing the reference's
glasses. Adding an explicit exemption for the head — full detail on face, hair
and glasses, drawn larger in frame, everything else obeying the chosen level —
produced a recognisable likeness on a page whose trees, path and clothes were
unchanged. Ink coverage went from 12.11% to 13.66% after `normalise_line_art`,
against the 35% mark where `too_much_ink` guidance fires.

**Objects need no exemption.** An invented teddy with a bald ear, an off-centre
stitched nose and one mismatched button eye came through at "2-3 years" with
every mark rendered as a closed shape to colour. A toy has no face to
genericise.

**A derived portrait is as good a reference as the photograph.** The same scene
drawn from the photograph and from the Doodle-drawn line portrait of the same
person produced equivalent likenesses. The portrait route is chosen for
consistency: the same drawn character appears in every picture rather than a
slightly different one each time.

**The badge rules had to be blunt.** Told to leave the corners empty, the model
filled them with scenery and added a border. Rewriting the instruction as an
explicit refusal ("Draw NOTHING in the corners: no background, no scenery, no
border, no frame, no circle") fixed it, and the same rewrite finally produced an
exaggerated caricature rather than a flattering portrait. Both prompt bodies are
reproduced in the plan.

**Fitting versus drawing for a circle.** `fit_inscribed` against a 50 mm safe
circle gives a 1024x1536 portrait drawing 27.7 mm across and a 1024x1024 square
one 35.4 mm. The free re-fit is honest; the paid redraw earns its place because a
picture composed for a page puts a small figure in a landscape the circle then
cuts away.

## Design

### A character store

New module `colouring_factory/characters.py`, following `storage.save_library_item`
exactly: `characters_root()` as a function so `DOODLE_DATA_DIR` monkeypatching
takes effect immediately, ids of `%Y%m%dT%H%M%SZ` plus eight hex characters,
folders created with `exist_ok=False`, fixed filenames, per-folder tolerance of
`OSError` and `JSONDecodeError` when listing, and the `root in resolved.parents`
traversal guard on delete.

```
~/.doodle/characters/<id>/
    photo.png       the uploaded picture, normalised
    portrait.png    the line-art portrait Doodle drew from it
    character.json  {id, name, kind, marks, created_at}
```

`kind` is `person`, `toy` or `character`. `marks` is a short sentence the user
writes: *curly hair to her shoulders, round glasses, a gap in her front teeth*.

The marks sentence is not decoration. A photograph carries tone and colour, both
of which a two-tone line drawing discards; what survives is shape, and words are
the right channel for shape. It is also the repair when a drawing misses, and the
only part of a character that still works if a provider declines the photograph.

Public API: `save_character`, `list_characters`, `load_character`,
`load_character_image`, `delete_character`, `prepare_photo`.

`prepare_photo(raw: bytes) -> bytes` applies EXIF rotation into the pixels,
strips every tag including GPS and the ICC profile by rebuilding the image from
raw pixel data, flattens transparency onto white, caps the long edge at 1536 px
and re-encodes as PNG. That last step makes true a claim `generators.py` has been
making falsely: it labels everything it sends as `image/png` regardless of the
bytes, which has been harmless only because every picture so far was one Doodle
drew.

`pillow-heif` joins `requirements.txt` with `register_heif_opener()` called once,
so a photograph straight off an iPhone opens at all. This bends the repo's rule
about new runtime dependencies; the exception is deliberate, because a photograph
feature that cannot open the format most family photographs are in is broken on
arrival.

### The drawing primitive

`refine_with_openai`, `refine_with_google`, `refine_with_recraft` and
`refine_with_provider` gain `reference_images: Sequence[bytes] = ()`, kept
separate from `image_bytes`. `image_bytes` is the picture being changed;
`reference_images` are pictures of characters to draw from. Either may be empty
but not both.

That separation is what lets `refine_with_provider` know a character was in a
request that came back refused, which is what makes the error message truthful.

`ProviderSpec` gains `max_reference_images: int = 0`. OpenAI 16, verified from
installed source. Google 4, from Google's documented limit of ten object plus four
character references for `gemini-3.1-flash-image`. Recraft 0. The control does not
appear when the number is zero, and a fourth provider is one row in the table.

OpenAI keeps its single-tuple form when there is exactly one picture, so
`tests/test_openai_wire.py` needs no change. Google's `input` list stops being a
two-element literal and becomes a text block followed by one image block per
picture, with the mime type derived from the bytes rather than asserted.

### The prompts

Two new builders in `prompts.py`, both carrying the existing colouring-book
contract and the chosen detail level.

`build_character_scene_prompt(...)` names each character, says which reference
picture is which, includes each one's marks, and adds the likeness rule and the
face exemption when any character is a person.

`build_caricature_prompt(...)` produces a head-and-shoulders caricature with the
blunt empty-corners rule and the exaggeration language that worked.

Three rules carry verbatim because each was arrived at by test rather than by
taste:

- *Draw hair as one or two large closed shapes that follow its real shape and
  length, never as separate strands.* Strands a pixel wide lose roughly a fifth
  of their ink to the `despeckle_size=3` median filter in the quick path.
- The face exemption, which overrides the reader profile for the head only.
- The empty-corners refusal for badges.

`colouring_factory/prompts.py:173` is deleted — "Do not imitate or reproduce an
existing television, film, book or game character". It contradicts the feature,
and the owner's decision is that a hobby app drawing cartoons at home for one
family needs no such rule. The single assertion at `tests/test_prompts.py:40`
goes with it, and `guidance.py:76-79` is reworded so a refusal is attributed to
the provider's own filter rather than to a Doodle rule that no longer exists. The
word "original" at `prompts.py:163` stays; it shapes the drawing rather than
prohibiting a subject.

### The homepage

A fourth item on the grey settings line under *Draw it*, opening an `st.popover`
like the other three, so nothing opens in place and nothing below it moves. The
label is a **count** — `nobody`, `1 character`, `2 characters` — never a joined
list of names: the settings line uses `flex: 0 0 auto` with `white-space: nowrap`
and `text-overflow: clip` inside a `.block-container` carrying
`overflow: visible !important`, so one long label pushes the page sideways on a
phone.

The panel shows each character by their portrait with a tick box, and an *Add
someone* button routing to a new `characters` screen for the picture, the name,
the marks and the plain statement of what leaves the computer.

The selection lives in a plain session key, not in per-name widget keys.
Streamlit garbage-collects a widget key the moment its widget is not rendered, so
ticking a character, visiting the add screen and coming back loses every tick;
`setdefault` does not help. Each checkbox takes `value=name in chosen` from the
plain key, the way `pair_grown_up` already does.

### Making a cartoon

Adding a character draws their caricature, and that caricature is an ordinary
doodle: it goes through `_adopt_artwork`, gets the A4 PDF, the badge strip,
printing, saving and *Colour it in for me*. The standalone cartoon feature and
the put-me-in-the-scene feature are one mechanism with two doors, so neither can
drift from the other.

### The badge strip

Beneath the finished picture on the result screen, following the pattern
`_render_grown_up_sheet` established: prepared eagerly inside `_quick_generate`,
parked in plain session keys, rendered by a self-guarding function that returns
early when its keys are empty, with unique widget keys so download buttons do not
collide.

It shows the picture already fitted to a 58 mm badge, free and instant, and
offers *Draw it for a badge* as a button naming its cost. The strip loads its own
`CalibrationProfile`, because the profile is read only after the result screen's
`st.stop()`. The redraw uses `target="Round badge"` and the provider's square
size, which the homepage path has never used.

This also fixes an existing incoherence: the homepage hard-codes
`target="A4 page"` and `size=spec.portrait_size`, so choosing the "Badge portrait"
style there gives badge composition instructions on a tall canvas.

### When a provider refuses

Whether a provider accepts a photograph of a real child cannot be established
without sending one, so the refusal is designed for rather than hoped against. A
new code `photo_declined` is raised by `refine_with_provider` when a `content`
refusal comes back from a request that carried reference pictures, with its own
guidance entry. Today such a refusal would tell the user to stop naming
characters from television and point them at the idea box.

## Blockers to clear first

Verified against commit `9a2ade2` on 2026-08-30. Each was proved by running code,
not by reading.

1. **`tests/test_guidance.py:13`** derives raisable codes by regexing the source
   of `generators.py` and `variations.py` only. A new module raising an unknown
   code passes 15 of 15; the identical raise added to `generators.py` fails
   correctly. Widen the helper to walk every module in `colouring_factory/` plus
   `app.py` before `characters.py` raises its first code.
2. **`tests/test_ui_conventions.py:89`** — `_all_labels` misses `file_uploader`,
   `toggle` and `multiselect`. Adding `file_uploader` immediately fails on the
   existing label "Upload PNG, JPG or WebP artwork"; fix it in the same commit.
   `_every_screen()` claims six screens and sweeps four.
3. **The router has no `else`.** Setting `screen="characters"` renders the full
   Studio with no error, so the new screen needs its own branch, a default in
   `_initialise_state`, and a decision in `_start_new_doodle`.
4. **`_render_first_result` has no `None` guard**, so any path setting
   `screen="result"` without preparing outputs raises `TypeError` from
   `hashlib.sha256(None)`.
5. **The version chain survives a new doodle.** `_start_new_doodle` clears 21
   keys but not `doodle_versions` or `current_version`, and the demo branch never
   calls `_start_version_chain`. A refine after a demo doodle acts on the previous
   picture. Fix before the badge redraw builds on the chain.

## Testing

No test makes a network call or spends money. Anything a user sees is asserted
through `streamlit.testing.v1.AppTest` against the real runtime, never the
hand-written fake in `test_app_smoke.py`, and every new button is clicked with its
effect asserted rather than merely asserted to exist.

`AppTest` reaches widgets inside an `st.popover`, and a checkbox list plus a
button that changes screen and reruns both work there. This was proved before the
design depended on it.

Named tests: photograph preparation including a JPEG carrying a real GPS block
and a `Make` tag; the character store round-tripping and surviving a deleted id
in settings; each prompt builder carrying its three verbatim rules; the OpenAI
multipart body carrying one part per reference picture; the Gemini body carrying
one image block per reference picture; the picker keeping its ticks across a
navigation; the badge strip rendering and its redraw button; `photo_declined`
having guidance whose cause does not mention wording and whose control is not the
idea box.

Baseline before this work: 274 passed in 23 seconds. Note `pyproject.toml` already
sets `addopts = "-q"`, so passing `-q` again swallows the count.

## Judgement calls

Two decisions were taken deliberately against a more cautious default, on the
owner's instruction that Doodle is a home-made app with exactly one user.

The uploaded photograph is **kept** on disk. An earlier draft deleted it once the
portrait was approved, on privacy grounds; a photograph in `~/.doodle` on the
owner's own Mac is no more exposed than the same photograph in Downloads, and
keeping it means a portrait can be redrawn without asking for the picture again.

A person is **always** drawn at full facial fidelity. There is no setting that
turns it down and no fallback to the chosen detail level, because the purpose of
the feature is that a child sees herself rather than a generic stand-in.

## Risks

- Whether a provider accepts a photograph of a real child is unknown and cannot
  be tested without sending one. Mitigated by `photo_declined` and by the marks
  sentence, which still draws the character from words alone.
- Google's multi-reference support is documented but untested on this account;
  there is no Gemini key on this machine. Marked as an assumption, not a fact.
- Likeness quality varies run to run. Mitigated by the marks sentence being
  editable and by redrawing costing one generation.
