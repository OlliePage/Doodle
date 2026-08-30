# Doodle QA improvements — design

Date: 2026-08-30
Branch: `claude/doodle-qa-improvements`
Status: approved for planning

## Why

Doodle makes colouring pages for toddlers. Five problems were reported from real use:

1. Nothing in the app explains how to add an API key, and generation is locked to OpenAI.
2. Warnings and errors state a problem without guiding the user to the control that fixes it.
3. On the homepage prompt bar, Streamlit's built-in right-hand affordances collide with each other
   and with the pill's rounded edge.
4. Variants of one idea come back near-identical rather than as different interpretations.
5. Circle (badge) output gives no sight of the boundaries, and artwork is silently clipped.

Three uncommitted files in `~/Developer/edits to doodle` already address points 1 to 3 in part.
They are folded in here as the starting point, with their gaps closed.

## Current state, verified 2026-08-30

Read from the repository at commit `b0b21b0`, and from the loose edits copied into a scratch
checkout and exercised with `pytest`.

- `colouring_factory/generators.py` exposes only `generate_with_openai`. The model dropdown in
  `app.py` is a hardcoded list of three OpenAI models.
- The API key is read from `OPENAI_API_KEY` or a sidebar password box. The sidebar starts
  collapsed (`initial_sidebar_state="collapsed"`), so a new user never sees it. `save_settings`
  persists only the printer calibration, so the key is retyped every launch.
- A first-run screen at `app.py:359-447` is unreachable: the `first_run` flag is initialised to
  `False` at line 184 and nothing sets it to `True`.
- Variant prompts differ by one appended sentence ("vary the pose or prop"), which is why the
  images come back near-identical.
- `pdf_export.py:236` scales artwork to fill the square bounding the safe circle, then clips to
  the ellipse, so the corners of the picture are cut away without warning.
- Streamlit 1.62 renders the hint as `data-testid="InputInstructions"` and the clear control as
  `stTextInputClearButton`, both right-aligned inside the input.

### What the loose edits already fix

Applied to a scratch checkout, 21 of 23 tests pass. The two failures
(`test_fresh_app_opens_on_minimal_doodle_homepage`, `test_doodle_brand_and_minimal_homepage_are_present`)
assert on renamed internals (`studio_open`, the literal `_doodle_logo("hero")`), not on broken
behaviour. They are change-detectors and are rewritten by this work, not worked around.

The edits add `providers.py` (a provider registry), `credentials.py` (keys saved to
`~/.doodle/credentials.json` with owner-only permissions), a dedicated connection screen with
links to each vendor's key and billing pages, a no-cost credential check, a classified error
type, and routing of key-related failures to the connection screen. They also replace the broken
`first_run` boolean with a `screen` state machine, ending the silent substitution of a demo
picture when no key is present. They leave points 4 and 5 untouched; the circle-sheet code is
byte-identical to the current version.

## Decisions taken

| Question | Decision |
|---|---|
| Provider line-up | OpenAI, Recraft, Google Gemini |
| Variation method | A text model writes N distinct scene briefs before drawing |
| Brief writing without a text model | Fall back to curated variation axes |
| Badge fit | Inscribe the artwork fully inside the safe circle, with a live preview |

## Design

### 1. Provider layer

`colouring_factory/providers.py` keeps its `ProviderSpec` registry and gains a Google Gemini
entry. Two fields are added to every spec:

- `text_model: str` — the vendor's text model used to write variation briefs; empty when the
  vendor has none.
- `supports_seed: bool` — whether the image endpoint accepts a deterministic seed.

`colouring_factory/generators.py` gains `generate_with_google`, and `generate_with_provider`
dispatches to it. `check_provider_connection` gains a Google branch that validates a key without
generating a paid image.

Google is the only one of the three with a free tier, so it is also the answer to "I do not want
a card on file". OpenAI stays the default.

[ASSUMPTION] The Gemini image model identifier and endpoint shape must be read from Google's
live API documentation during implementation. Model names in training data are stale and must
not be guessed.

### 2. Variation diversity

New module `colouring_factory/variations.py`, with one public entry point:

```
build_variation_briefs(concept, count, *, provider_id, api_key) -> tuple[str, ...]
```

It returns exactly `count` one-line scene briefs, each a different interpretation of `concept`.

Where the provider has a `text_model`, it asks that model for the briefs, instructing it to vary
four things — the moment in the story, the camera framing, the setting, and the mood — and
forbidding it from restating the concept unchanged. The response is validated: exactly `count`
briefs, none empty, none duplicated after normalisation. A failed or malformed response falls
back rather than raising, because a weaker variation is better than no picture.

Where the provider has no `text_model`, or the call fails, it composes briefs from
`VARIATION_AXES`: a curated tuple of framings, story moments, settings and moods. Selection is
deterministic given `(concept, count)`, so the same idea reproduces the same fallback set.

`build_colouring_prompt` in `prompts.py` gains a `variation_brief: str = ""` parameter. When
present it replaces the bare concept as the scene description. Style, age and composition rules
are identical across variants, so what differs between them is the interpretation.

`generate_with_provider` takes `prompts: Sequence[str]` instead of one `prompt` plus a variant
count, making the caller responsible for distinctness and the generator responsible only for
drawing. The existing `_variant_prompt` helper is deleted.

### 3. Badge boundaries

Three parts.

**Geometry.** `layouts.py` gains:

```
fit_inscribed(source_width, source_height, centre_x, centre_y, ellipse_width, ellipse_height)
```

returning `(x, y, width, height)` in the same convention as the existing `fit_contain`: the
largest rectangle of the source's aspect ratio that fits wholly inside the ellipse.
For a source of aspect ratio `r` inside a circle of diameter `d`, the inscribed width is
`d / sqrt(1 + 1/r²)`. For a square source this is `d / sqrt(2)`, about 70.7 per cent of the
diameter, so the artwork is smaller than today by design.

**Configuration.** `CircleSheetConfig` gains `fit_mode: str = "inscribe"`, accepting `"inscribe"`
or `"fill"`. `"fill"` reproduces the current clip-the-corners behaviour, so existing sheets stay
reproducible. `pdf_export.create_circle_sheet_pdf` selects between `fit_inscribed` and the
existing `fit_contain` accordingly. Clipping to the ellipse stays in both modes as a safety net.

**Preview.** New module `colouring_factory/badge_preview.py`:

```
render_badge_preview(image_bytes, config, calibration) -> bytes
```

returns a PNG of one badge at true proportions, with the cut, finished and safe diameters drawn
as distinguishable concentric rings and the artwork placed exactly as the PDF will place it. It
is rendered by producing a single-badge PDF through the existing export path and rasterising it
with the existing `preview.render_pdf_preview`, so the preview cannot drift from the output.
The studio shows it live in the circle-sheet section, before the Build button.

**Generation.** `TARGET_RULES["Round badge"]` in `prompts.py` is strengthened to ask for a
composition built for a circular crop, so badge artwork is generated badge-shaped rather than
rescued afterwards.

### 4. Error and warning guidance

New module `colouring_factory/guidance.py` holding:

```
@dataclass(frozen=True)
class Guidance:
    title: str          # what went wrong, in one short phrase
    cause: str          # why, in plain English
    fix: str            # what to do about it
    control: str        # the exact named setting or screen the fix lives in
    action_label: str   # empty when no one-click fix is possible
```

and `guidance_for(code: str, **context) -> Guidance`. An unrecognised code returns a generic
entry naming the Settings sidebar rather than `None`, so the caller never has to branch and no
failure can reach the user unexplained. `**context` carries values interpolated into `fix` and
`action_label`, such as the largest margin that would let the requested circles fit.

Every error code raised by `generators.py` gets an entry, as do the layout and processing
conditions that currently render as bare messages: no circles fitting the sheet, a safe diameter
larger than the finished diameter, ink coverage above 35 per cent, ink coverage below 0.4 per
cent, and a PDF that fails to build.

`app.py` renders one guidance panel component for all of them. Key-related codes keep the
existing routing to the connection screen. The rest name the responsible control and, where a
correction is computable, offer a button that applies it — reducing the outer margin to a value
that fits, or lowering the threshold. Streamlit cannot scroll to a widget reliably, so a
one-click correction replaces navigation rather than supplementing it.

### 5. Homepage prompt bar

The loose edits hide both `InputInstructions` and the clear button inside the pill, removing the
collision and the affordance together. That CSS stays, and a static line is added below the bar
reading "Press Enter to draw". It lives outside the pill, so it cannot collide with anything, and
it restores the signal that Enter submits.

## Testing

Provider calls are stubbed throughout; no test spends money.

- `fit_inscribed` output verified against the ellipse equation for square, portrait and landscape
  sources, and asserted to be strictly smaller than `fit_contain` for the same box.
- `build_variation_briefs` returns exactly `count` briefs, no duplicates after normalisation, and
  falls back to axes for a provider with no text model, for a malformed response, and for a
  raised exception.
- Fallback briefs are deterministic for the same `(concept, count)` and differ across counts.
- `build_colouring_prompt` places the variation brief as the scene and leaves style, age and
  composition rules unchanged between variants.
- Every error code constructible from `generators.py` has a `guidance_for` entry.
- The provider registry is internally consistent: every spec has a non-empty label, env var, key
  URL, default model within its own model tuple, and both sizes populated.
- `create_circle_sheet_pdf` in inscribe mode leaves no ink outside the safe circle for a
  full-bleed test image; in fill mode it reproduces today's geometry.
- `render_badge_preview` returns a decodable PNG whose ring positions match the plan.
- The two rewritten homepage tests assert behaviour: the app halts on a homepage carrying the
  hero wordmark and exactly one prompt input, and submitting a prompt advances off the homepage.
  They no longer assert internal function or state-key names.

Existing PDF geometry, calibration and processing tests must continue to pass unchanged.

## Out of scope

- A local or self-hosted image model, and a custom OpenAI-compatible endpoint.
- Encrypting `credentials.json` or moving keys into the macOS keychain. It is a single-user local
  app; owner-only file permissions are the chosen level.
- Vector (SVG) output. Artwork stays raster, as recorded in the README's MVP boundaries.
- Automated scoring of drawing complexity or anatomy.
