# Provider-agnostic image generation with iterative refinement

Date: 2026-08-30
Status: Approved for planning

## Problem

Doodle can generate a colouring page but cannot change one. If a picture is
right apart from one figure standing in the wrong place, the only recourse is
to regenerate the whole thing from the original idea and hope the rest survives.

Separately, OpenAI is hardcoded in five places — the `OPENAI_API_KEY`
environment lookup, the sidebar key field, the model dropdown, the quick
generate call, and the `generate_with_openai` function name itself. Adding a
second provider today means touching all five and adding a sixth vendor-named
function. The refinement feature must not be built on that foundation.

## Goals

1. A provider seam so any image model can be plugged in by writing one class.
2. Two working providers: OpenAI (ported, behaviour unchanged) and Gemini.
3. Refine a generated doodle with a follow-up instruction, keeping a version
   history you can step back through.

## Non-goals

- Brush masks for region-precise editing. Wanted eventually; explicitly
  deferred. The interface reserves an optional mask argument so adding it later
  does not change the interface.
- Local or self-hosted models, and aggregators such as Replicate. The registry
  makes these additive later.
- Automatic failover between providers.

## Verified provider facts

Both checked against live documentation on 2026-08-30.

| | OpenAI | Gemini |
|---|---|---|
| Package | `openai` | `google-genai` |
| Generate | `client.images.generate` | `client.interactions.create` |
| Edit | `client.images.edit` | same call, image passed as an input part |
| Edit models | `gpt-image-2` (and `-1.5`, `-1`) | `gemini-3.1-flash-image`, `gemini-3-pro-image` |
| Size | pixels, e.g. `1024x1536` | aspect ratio (`3:4`) plus tier (`1K`/`2K`/`4K`) |
| Quality | `low`/`medium`/`high` | no equivalent |
| Image bytes | `b64_json` or a URL | `interaction.output_image.data`, base64 |

The size and quality mismatch is the reason the seam needs a capability record
rather than a shared function signature.

## Architecture

### The interface

A new module `colouring_factory/providers/` replaces `generators.py`. It defines
one protocol that every provider implements:

```
generate(prompt, *, page_shape, quality, variants) -> list[GeneratedArtwork]
edit(image_bytes, instruction, *, page_shape, quality, mask_bytes=None)
    -> GeneratedArtwork
```

`GeneratedArtwork` is the existing dataclass and does not change, so processing,
PDF export and the library are untouched.

`page_shape` is the key abstraction. Callers ask for a semantic shape — `PORTRAIT_A4`
or `SQUARE` — and each adapter translates it into its own vocabulary. OpenAI
turns `PORTRAIT_A4` into `1024x1536`; Gemini turns it into aspect ratio `2:3` at
the `1K` tier. Callers never speak pixels or ratios.

`quality` is a three-level enum (`LOW`, `MEDIUM`, `HIGH`). Adapters whose model
has no quality concept ignore it. This is deliberate: a provider silently
ignoring a hint is better than callers branching on provider identity.

### The capability record

Each provider ships a frozen dataclass declaring: display name, the credential
environment variable it reads, its available model identifiers, whether it
supports editing, and whether it supports masks. The sidebar builds its dropdowns
from this record, and the refine box hides itself when `supports_edit` is false.
No user-interface code may branch on a provider's name.

### The registry

A dictionary mapping provider identifier to factory, plus `available_providers()`
which returns those with a usable credential. Adding a provider is one new module
and one registry entry.

### Credentials

Keys are stored in the existing `~/.doodle/settings.json` under a `providers` key,
keyed by provider identifier. Precedence on read is environment variable first,
then saved settings — so a shell export always wins and can override a stale saved
key. Keys are written only when the user submits the sidebar form. The settings
file is created with permissions `0600`.

This file is on the user's own machine and is not encrypted. That is an accepted
trade-off for a local single-user tool, and the sidebar states plainly where keys
are stored.

### Version history

Session state gains `doodle_versions`: an ordered list of entries, each holding a
`GeneratedArtwork`, the instruction that produced it (empty for the original),
and the index of the version it was derived from. Picking a candidate from the
gallery starts a fresh chain. Each refinement appends.

History is append-only. Selecting an earlier version makes it the base for the
next refinement without deleting anything that came after, so exploring a
direction and backing out never destroys work. A thumbnail strip beneath the
picture shows the chain, the current version highlighted.

### Keeping the style intact

An instruction sent bare would lose the colouring-book rules and return shading
or grey fill. `prompts.py` gains `build_refinement_prompt(instruction, style_name)`
wrapping the instruction in the same style contract `build_colouring_prompt`
enforces — black outlines, white background, no shading — plus an explicit
instruction to leave everything else in the scene unchanged.

## Expected behaviour and its limits

Without a mask, both providers redraw the whole picture. Unchanged parts return
close to the original but not pixel-identical, and a detail will occasionally
drift. The user interface states this next to the refine box so the behaviour is
not mistaken for a fault. Region-stable editing requires the deferred mask work.

## Error handling

`ProviderError` replaces `GeneratorError`, raised for a missing credential, a
missing client package, a refused request, or an empty response. Provider
adapters catch their own SDK's exceptions and re-raise as `ProviderError` with
the provider named, so the user interface never sees a vendor exception type.

Refinement failure leaves the version chain untouched and shows the error above
the refine box, so a failed edit costs nothing.

## Testing

Existing generator tests stub the client object entirely; that pattern continues,
so no test makes a network call. Coverage to include:

- each adapter sends the expected request shape for generate and for edit
- both base64 and URL response forms decode (OpenAI)
- `page_shape` maps correctly per provider, including that the same shape yields
  `1024x1536` for OpenAI and aspect `2:3` for Gemini
- missing credentials, missing SDK package and empty responses all raise
  `ProviderError` naming the provider
- the registry lists only providers with a usable credential
- refinement prompts retain the style contract
- version chain: appending, selecting an earlier version, and that a failed
  refinement leaves the chain unchanged

## Migration

`generate_with_openai` is removed rather than deprecated. Doodle is a
single-user local application with no external consumers, so a compatibility
shim would be dead code. `tests/test_generators.py` is replaced by per-provider
test modules.

## Risks

- **Gemini SDK shape.** Documentation was read, not executed. The first
  implementation task is a throwaway probe against the live API to confirm the
  response object before the adapter is written.
- **Refinement cost.** Each refinement is a full image charge. The version strip
  makes repeated iteration easy, so the user interface shows the count of
  versions generated in the current chain.
- **Style drift over a long chain.** Each refinement redraws from the previous
  output, so errors compound across many steps. Not mitigated in this work;
  worth watching once real use starts.
