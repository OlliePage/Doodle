# Refining a doodle — design

Date: 2026-08-30
Branch: `claude/refine-doodles`
Status: approved for planning
Supersedes: the refinement third of the closed [#1](https://github.com/OlliePage/Doodle/pull/1)

## Problem

Doodle can draw a colouring page but cannot change one. If a picture is right
apart from one thing — the dinosaur should wear wellingtons, the fire engine is
too close to the edge — the only recourse is to regenerate from the original
idea and hope the rest survives. With variations now coming back genuinely
different from one another, that gamble costs more than it used to: regenerating
no longer returns something close to what you had.

This is the one goal of the closed #1 that was not built. Its other two, a
provider seam and a second provider, shipped in #4 and #8 on 2026-08-30.

## What already exists

- `colouring_factory/providers.py` — a frozen `ProviderSpec` registry for
  OpenAI, Google Gemini and Recraft, carrying each vendor's models, image sizes,
  credential variable and setup copy.
- `colouring_factory/generators.py` — `generate_with_provider(...)` taking one
  prompt per picture, and `GeneratorError` with a `code` field.
- `colouring_factory/guidance.py` — every error code mapped to a cause, a fix and
  the control that owns it.
- `colouring_factory/credentials.py` — keys on disk at `~/.doodle/credentials.json`
  with owner-only permissions.
- A `screen` state machine in `app.py` with a result screen already carrying a
  "Make a change" text box that currently rewrites the original idea and
  regenerates from scratch.

## Goals

1. Change a generated picture with a written instruction, without redrawing it
   from the original idea.
2. Keep every version, so backing out of a direction destroys nothing.
3. Work on all three providers, all of which support editing.

## Non-goals

- Brush masks for region-precise editing. Wanted eventually, deferred here. The
  interface reserves an optional `mask_bytes` argument so adding it later does
  not change the signature.
- Refining an uploaded or demo picture. Only generated artwork carries the
  provider and model it came from, and refining needs both.
- Automatic failover between providers.

## Verified provider facts

Read from live documentation on 2026-08-30. All three support editing, so no
provider needs the refine control hidden — but the capability is declared per
provider anyway, so a future addition that cannot edit is handled without
branching on a provider's name.

| | OpenAI | Google Gemini | Recraft |
|---|---|---|---|
| Endpoint | `client.images.edit` | `POST /v1beta/interactions` | `/v1/images/imageToImage` |
| Image passed as | multipart file | a `{"type": "image", "mime_type", "data"}` block beside the text block | multipart file |
| Mask | optional | not applicable | separate inpainting endpoint |
| Fidelity control | `input_fidelity` | none | `strength` |

Gemini uses the same endpoint and models for editing as for generation; the
input becomes a two-element list rather than one. OpenAI's `input_fidelity`
parameter controls how closely the result tracks the original and directly
addresses the drift described below, so it is set high.

[ASSUMPTION] Recraft's exact image-to-image path and parameter names are taken
from its endpoint index rather than a worked example. The first implementation
task confirms them against the live API reference before the adapter is written.

## Design

### Capability

`ProviderSpec` gains two fields:

- `supports_edit: bool` — whether the provider can change an existing image.
- `edit_fidelity_param: str` — the name of its fidelity control, empty where
  there is none. Kept as data so `generators.py` sets it without an if-else on
  the provider's identity, which is the mistake that gave Gemini users Recraft's
  instructions.

### Editing

`generators.py` gains one public function mirroring the generation one:

```
refine_with_provider(*, provider_id, api_key, image_bytes, prompt, model,
                     size, quality="medium", mask_bytes=None) -> GeneratedArtwork
```

with `refine_with_openai`, `refine_with_google` and `refine_with_recraft` behind
it. Each catches its own vendor's failures and re-raises `GeneratorError` with
the provider named and a `code`, so the interface never sees a vendor exception.
Two new codes, `edit_unsupported` and `edit_failed`, get guidance entries; the
existing test asserting every raised code has guidance covers them.

### Keeping the style intact

An instruction sent bare loses the colouring-book contract and comes back shaded.
`prompts.py` gains:

```
build_refinement_prompt(instruction, *, style_name, age_profile, target) -> str
```

wrapping the instruction in the same rules `build_colouring_prompt` enforces —
black outlines only, white background, no shading or grey — plus an explicit
direction to change only what was asked and leave the rest of the scene alone.

### Version history

New module `colouring_factory/history.py`, so the chain is testable without
Streamlit:

```
@dataclass(frozen=True)
class Version:
    artwork: GeneratedArtwork
    instruction: str        # empty for the original
    parent: int | None      # index of the version it was derived from

append(chain, version) -> tuple[Version, ...]
start(artwork) -> tuple[Version, ...]
```

The chain is append-only. Selecting an earlier version makes it the base for the
next refinement without deleting what came after, so exploring a direction and
backing out never destroys work. Choosing a different candidate from the
generation gallery starts a fresh chain.

`app.py` holds the chain in `st.session_state.doodle_versions` and shows a
thumbnail strip beneath the picture with the current version marked. Each
thumbnail's caption is its instruction, so the strip reads as the history of
what was asked for.

### The interface

The result screen's existing "Make a change" box stops rewriting the original
idea and regenerating. It refines the current version instead. Beneath it sits a
plain statement of the limitation below, and a count of versions in the current
chain, because each refinement is a full image charge.

The studio gains the same control under the chosen artwork.

## The limitation, stated plainly

Without a mask, all three providers redraw the whole picture. Unchanged parts
come back close to the original but not pixel-identical, and a detail will
occasionally drift. OpenAI's `input_fidelity` reduces this and is set high;
Gemini and Recraft have no equivalent lever exposed here.

The interface says so next to the refine box, in those words, so the behaviour is
not mistaken for a fault. Style drift also compounds across a long chain, since
each refinement redraws from the previous output rather than the original. Not
mitigated here; the version strip at least makes it visible and lets the user
step back to a cleaner ancestor.

## Testing

No test makes a network call or spends money; provider calls are stubbed as the
existing generator tests do.

- Each adapter sends the expected request shape for a refinement, and passes the
  image in that vendor's form.
- A missing credential, a missing client package and an empty response each raise
  `GeneratorError` naming the provider, with a code that has guidance.
- `build_refinement_prompt` keeps the style contract and carries the instruction.
- The chain appends; selecting an earlier version leaves later versions in place;
  a failed refinement leaves the chain unchanged.
- Driven through `AppTest` on the real runtime, not the hand-written fake:
  submitting an instruction advances the chain and the strip renders; an empty
  instruction does nothing; **the refine control is clicked, not merely asserted
  to exist**, and the version count afterwards is checked.

That last point is the lesson of #8: a recovery button shipped broken past a test
that checked only that it rendered.

## Decided: show the count, do not cap

Refining costs a full image generation each time, and the version strip makes
iterating easy. Doodle shows the number of versions in the current chain beside
the refine box and leaves the judgement to the user. No cap, no warning
threshold, because a threshold is a guess at someone else's budget and a cap
blocks work at the moment it is going well.
