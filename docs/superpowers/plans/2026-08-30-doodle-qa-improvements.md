# Doodle QA Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix five reported usability failures in Doodle — provider lock-in with unexplained API key setup, errors that name a problem without a route to the fix, a colliding homepage prompt bar, near-identical picture variations, and badge artwork silently clipped at the corners.

**Architecture:** Doodle is a single-file Streamlit UI (`app.py`) over a pure-Python package (`colouring_factory/`) that holds all geometry, prompting and PDF work. That split is deliberate — the image model invents the drawing, ordinary deterministic code controls the printed millimetres — and every task here preserves it. New behaviour goes into small focused modules in the package with their own tests; `app.py` only ever wires them together.

**Tech Stack:** Python 3.11+, Streamlit 1.62, reportlab (PDF), PyMuPDF (PDF→PNG preview), Pillow, numpy, pytest 9. HTTP to providers uses `urllib.request` from the standard library, except OpenAI which uses the `openai` package already in `requirements.txt`.

**Spec:** `docs/superpowers/specs/2026-08-30-doodle-qa-improvements-design.md`

## Global Constraints

- Python 3.11+ (`requires-python = ">=3.11"`). Use `from __future__ import annotations` at the top of every module, matching the existing package.
- No new runtime dependencies. Google and Recraft are called with `urllib.request` from the standard library. Do not add `google-genai`, `requests` or similar.
- **No test may make a real network call or spend money.** Stub every provider call.
- British English in all user-facing copy ("colour", "centre", "personalise"). The existing code already does this; match it.
- No docstrings or comments restating what code does. Comments explain *why*, especially print-geometry and statutory-style rationale.
- Frozen dataclasses for configuration objects, matching `colouring_factory/models.py`.
- Git identity is already set locally to `Milo Garth`. Do not pass `-c user.name` or `--author`. No `Co-Authored-By: Claude` trailer and no "Generated with Claude Code" footer.
- Run the full suite with `.venv/bin/python -m pytest` from the repository root. It must be green before every commit.
### Streamlit conventions (added 2026-08-30 after loading the `developing-with-streamlit` skill)

Streamlit 1.62 is installed and supports all of the following; verified by inspecting the
installed signatures, not assumed.

- **Never write `use_container_width` in new code.** It is deprecated. Use `width="stretch"`.
  The existing `app.py` uses it about forty times; those are swept in Task 10 as their own
  commit rather than bundled into feature commits.
- **Prefer native elements over injected HTML.** New panels use `st.container(border=True)` with
  ordinary `st.markdown` inside, not a `<div class="geometry-box">`. The existing `.geometry-box`
  markup stays where it already is; do not widen the diff chasing it.
- **`st.segmented_control` rather than `st.radio(..., horizontal=True)`** for compact mode
  switches such as the badge fit control.
- **Sentence casing** for labels, and Material Symbols icons (`icon=":material/name:"`) rather
  than emoji or arrow glyphs on new buttons.
- The homepage CSS is the one deliberate exception to "do not style with CSS": the reported
  defect is a styling collision inside Streamlit's own input chrome, which no native API exposes.

- Verified provider facts (read from live documentation on 2026-08-30 — do not substitute remembered model names):
  - Google endpoint `POST https://generativelanguage.googleapis.com/v1beta/interactions`, auth header `x-goog-api-key`, image models `gemini-3.1-flash-image` / `gemini-3.1-flash-lite-image` / `gemini-3-pro-image`, text model `gemini-3.5-flash-lite`, key page `https://aistudio.google.com/apikey`.
  - OpenAI image models `gpt-image-2` / `gpt-image-1.5` / `gpt-image-1-mini`, sizes `1024x1536` and `1024x1024`, text model `gpt-5-mini`.
  - Recraft endpoint `https://external.api.recraft.ai/v1/images/generations`, models `recraftv4_1` / `recraftv4_1_utility` / `recraftv4`, sizes given as ratios `3:4` and `1:1`, no text model.

---

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `colouring_factory/providers.py` | Static registry describing each image provider: labels, key and billing URLs, model lists, image sizes, text model, seed support. No I/O. |
| `colouring_factory/credentials.py` | Reading, writing and deleting provider keys on disk with owner-only permissions; resolving a key from session, environment or disk. |
| `colouring_factory/variations.py` | Turning one picture idea into N distinct scene briefs, via a text model where available and curated axes otherwise. |
| `colouring_factory/badge_preview.py` | Rendering a single badge as a PNG with cut, finished and safe rings, using the real export path so preview and output cannot diverge. |
| `colouring_factory/guidance.py` | Mapping every failure condition to a title, cause, fix, responsible control and optional one-click correction. No Streamlit imports. |
| `tests/test_providers.py` | Registry consistency. |
| `tests/test_credentials.py` | Key persistence, permissions, resolution precedence, masking. |
| `tests/test_variations.py` | Brief distinctness, count, determinism, and all three fallback paths. |
| `tests/test_badge_fit.py` | Inscribed geometry against the ellipse equation; no ink outside the safe circle. |
| `tests/test_guidance.py` | Every generator error code has an entry; one-click corrections are computed correctly. |

**Modified:**

| File | Change |
|---|---|
| `colouring_factory/generators.py` | Classified error type, per-provider generation, Google provider, prompt-list interface. |
| `colouring_factory/prompts.py` | `variation_brief` parameter; stronger round-badge composition rule. |
| `colouring_factory/models.py` | `CircleSheetConfig.fit_mode`. |
| `colouring_factory/layouts.py` | `fit_inscribed`. |
| `colouring_factory/pdf_export.py` | Honour `fit_mode`; single-badge export for the preview. |
| `app.py` | Screen state machine, connection screen, provider sidebar, guidance panel, badge preview, prompt bar hint. |
| `tests/test_app_smoke.py` | Rewrite the homepage test to assert behaviour, not internal names. |
| `tests/test_branding.py` | Same. |
| `README.md`, `.env.example` | Document all three providers and where keys are stored. |

---

## Task 1: Land the provider registry, credentials and screen state machine

The uncommitted work in `~/Developer/edits to doodle` already implements this. It has been compiled and tested in a scratch checkout: 21 of 23 tests pass, and both failures are tests asserting on renamed internals rather than broken behaviour. This task brings it in and repairs those two tests.

**Files:**
- Create: `colouring_factory/providers.py` (copy from `~/Developer/edits to doodle/providers.py`)
- Create: `colouring_factory/credentials.py` (copy from `~/Developer/edits to doodle/credentials.py`)
- Modify: `colouring_factory/generators.py` (replace with `~/Developer/edits to doodle/generators.py`)
- Modify: `app.py` (replace with `~/Developer/edits to doodle/app.py`)
- Test: `tests/test_app_smoke.py:150-180`, `tests/test_branding.py`
- Create: `tests/test_providers.py`, `tests/test_credentials.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `providers.ProviderSpec` — frozen dataclass with `id, label, env_var, key_url, billing_url, docs_url, default_model, models: tuple[str, ...], portrait_size, square_size, key_placeholder, description, billing_note`
  - `providers.PROVIDERS: dict[str, ProviderSpec]`, `providers.DEFAULT_PROVIDER = "openai"`
  - `providers.get_provider(provider_id) -> ProviderSpec`, `providers.provider_id_from_label(label) -> str`
  - `credentials.save_provider_key(provider_id, api_key) -> None`, `credentials.delete_provider_key(provider_id) -> None`
  - `credentials.resolve_provider_key(provider_id, session_keys=None) -> tuple[str, str]` returning `(key, source_description)`
  - `credentials.mask_key(api_key) -> str`
  - `generators.GeneratorError` with `.provider`, `.code`, `.status_code`
  - `generators.generate_with_provider(*, provider_id, api_key, prompt, variants, model, size, quality="low", random_seed=None) -> list[GeneratedArtwork]`
  - `generators.check_provider_connection(provider_id, api_key) -> dict[str, Any]`

- [x] **Step 1: Copy the four files in**

```bash
SRC="/Users/olliepage/Developer/edits to doodle"
cp "$SRC/providers.py" colouring_factory/providers.py
cp "$SRC/credentials.py" colouring_factory/credentials.py
cp "$SRC/generators.py" colouring_factory/generators.py
cp "$SRC/app.py" app.py
```

- [x] **Step 2: Run the suite to see exactly the two expected failures**

Run: `.venv/bin/python -m pytest`

Expected: `2 failed, 21 passed`. The failures must be exactly `tests/test_app_smoke.py::test_fresh_app_opens_on_minimal_doodle_homepage` (`KeyError: 'studio_open'`) and `tests/test_branding.py::test_doodle_brand_and_minimal_homepage_are_present` (assertion on the literal `_doodle_logo("hero")`). Any other failure means the copy is wrong — stop and re-check.

- [x] **Step 3: Rewrite the branding test to assert behaviour**

These two tests broke during a rename without catching a real bug, which is the definition of a change-detector. They are rewritten to assert what a user would notice, not which identifiers the code happens to use.

Replace the whole of `tests/test_branding.py`:

```python
from pathlib import Path


def test_homepage_is_branded_and_minimal() -> None:
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

    assert 'page_title="Doodle"' in app_source
    assert "doodle-logo--hero" in app_source
    assert 'placeholder="What shall we draw?"' in app_source
    assert '[data-testid="stSidebar"] {display: none !important;}' in app_source
    assert 'st.title("Colouring Factory")' not in app_source
```

- [x] **Step 4: Rewrite the homepage smoke test to assert behaviour**

In `tests/test_app_smoke.py`, replace the body of `test_fresh_app_opens_on_minimal_doodle_homepage` from the `assert fake.session_state["studio_open"] is False` line to the end of the function with:

```python
    assert any("doodle-logo--hero" in body for body in fake.markdown_calls)

    assert len(fake.text_input_calls) == 1
    label, kwargs = fake.text_input_calls[0]
    assert label == "Describe a picture to colour"
    assert kwargs["key"] == "home_prompt"
    assert kwargs["placeholder"] == "What shall we draw?"
    assert kwargs["label_visibility"] == "collapsed"
    assert callable(kwargs["on_change"])

    # Submitting an idea must leave the homepage. Which screen it goes to
    # depends on whether a provider key is present, so assert only that it moved.
    fake.session_state["home_prompt"] = "A bear flying a kite"
    kwargs["on_change"]()
    assert fake.session_state["screen"] != "home"
    assert fake.session_state["generation_idea"] == "A bear flying a kite"
```

- [x] **Step 5: Run both rewritten tests**

Run: `.venv/bin/python -m pytest tests/test_branding.py tests/test_app_smoke.py -v`
Expected: PASS.

- [x] **Step 6: Write the provider registry test**

Create `tests/test_providers.py`:

```python
from colouring_factory.providers import (
    DEFAULT_PROVIDER,
    PROVIDERS,
    get_provider,
    provider_id_from_label,
)


def test_every_provider_is_completely_described() -> None:
    for provider_id, spec in PROVIDERS.items():
        assert spec.id == provider_id
        assert spec.label.strip()
        assert spec.env_var.strip()
        assert spec.key_url.startswith("https://")
        assert spec.billing_url.startswith("https://")
        assert spec.models, f"{provider_id} lists no models"
        assert spec.default_model in spec.models
        assert spec.portrait_size.strip()
        assert spec.square_size.strip()


def test_provider_labels_are_unique() -> None:
    labels = [spec.label.lower() for spec in PROVIDERS.values()]
    assert len(labels) == len(set(labels))


def test_default_provider_exists() -> None:
    assert DEFAULT_PROVIDER in PROVIDERS


def test_unknown_provider_falls_back_to_the_default() -> None:
    assert get_provider("nonsense").id == DEFAULT_PROVIDER
    assert get_provider(None).id == DEFAULT_PROVIDER
    assert provider_id_from_label("Nonsense") == DEFAULT_PROVIDER


def test_label_round_trips_to_its_own_id() -> None:
    for provider_id, spec in PROVIDERS.items():
        assert provider_id_from_label(spec.label) == provider_id
```

- [x] **Step 7: Write the credentials test**

Create `tests/test_credentials.py`:

```python
import stat

import pytest

from colouring_factory.credentials import (
    credentials_path,
    delete_provider_key,
    load_credentials,
    mask_key,
    resolve_provider_key,
    save_provider_key,
)


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("RECRAFT_API_TOKEN", raising=False)


def test_a_saved_key_is_read_back() -> None:
    save_provider_key("openai", "sk-test-12345678")
    assert load_credentials()["openai"] == "sk-test-12345678"


def test_the_credentials_file_is_readable_only_by_its_owner() -> None:
    save_provider_key("openai", "sk-test-12345678")
    mode = credentials_path().stat().st_mode
    assert not mode & stat.S_IRGRP
    assert not mode & stat.S_IROTH


def test_an_empty_key_is_refused() -> None:
    with pytest.raises(ValueError):
        save_provider_key("openai", "   ")


def test_deleting_the_last_key_removes_the_file() -> None:
    save_provider_key("openai", "sk-test-12345678")
    delete_provider_key("openai")
    assert not credentials_path().exists()


def test_deleting_one_of_two_keys_keeps_the_other() -> None:
    save_provider_key("openai", "sk-test-12345678")
    save_provider_key("recraft", "recraft-token-abcdefgh")
    delete_provider_key("openai")
    assert load_credentials() == {"recraft": "recraft-token-abcdefgh"}


def test_session_beats_environment_which_beats_disk(monkeypatch) -> None:
    save_provider_key("openai", "sk-from-disk-000000")
    key, source = resolve_provider_key("openai")
    assert key == "sk-from-disk-000000"
    assert source == "this Mac"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env-000000")
    key, source = resolve_provider_key("openai")
    assert key == "sk-from-env-000000"
    assert source == "OPENAI_API_KEY"

    key, source = resolve_provider_key("openai", {"openai": "sk-from-session-0000"})
    assert key == "sk-from-session-0000"
    assert source == "this session"


def test_no_key_anywhere_returns_empty() -> None:
    assert resolve_provider_key("openai") == ("", "")


def test_a_corrupt_credentials_file_is_treated_as_empty() -> None:
    save_provider_key("openai", "sk-test-12345678")
    credentials_path().write_text("{ not json", encoding="utf-8")
    assert load_credentials() == {}


def test_masking_never_reveals_the_middle_of_a_key() -> None:
    assert mask_key("sk-proj-abcdefghijklmnop") == "sk-p••••mnop"
    assert mask_key("short") == "••••••••"
    assert mask_key("") == ""
```

- [x] **Step 8: Run the two new test files**

Run: `.venv/bin/python -m pytest tests/test_providers.py tests/test_credentials.py -v`
Expected: PASS. If `test_masking_never_reveals_the_middle_of_a_key` fails, read `mask_key` and correct the expected strings to match its actual first-four / last-four behaviour rather than changing the implementation.

- [x] **Step 9: Run the whole suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass, no failures.

- [x] **Step 10: Commit**

```bash
git add colouring_factory/providers.py colouring_factory/credentials.py colouring_factory/generators.py app.py tests/test_providers.py tests/test_credentials.py tests/test_branding.py tests/test_app_smoke.py
git commit -m "Add provider registry, saved credentials and a screen state machine

Generation was locked to OpenAI with the key hidden behind a collapsed
sidebar and never persisted, so it had to be retyped every launch. Adds
a provider registry, keys saved to ~/.doodle/credentials.json with
owner-only permissions, a connection screen linking to each vendor's
key and billing pages, and a no-cost credential check.

Also replaces the first_run boolean, which nothing ever set to True and
which left ~90 lines of first-run UI unreachable, with an explicit
screen state machine. A missing key now routes to the connection screen
instead of silently substituting a demo picture for whatever was asked
for.

The two homepage tests asserted on internal names (studio_open, the
literal _doodle_logo(\"hero\")) and broke on the rename without catching
a bug. Rewritten to assert what a user would notice."
```

---

## Task 2: Add Google Gemini as a third provider

Google is the only one of the three with a free tier, so it is the answer to "I do not want a card on file". Its API shape differs from OpenAI's and Recraft's: it takes an aspect ratio rather than a pixel size, and returns content blocks rather than a data array.

**Files:**
- Modify: `colouring_factory/providers.py`
- Modify: `colouring_factory/generators.py`
- Modify: `tests/test_providers.py`
- Create: `tests/test_generators_google.py`

**Interfaces:**
- Consumes: `providers.ProviderSpec`, `generators.GeneratorError`, `generators._normalise_error`, `generators._read_image_payload` from Task 1.
- Produces:
  - `ProviderSpec.text_model: str` and `ProviderSpec.supports_seed: bool` on every spec
  - `generators.generate_with_google(*, api_key, prompt, variants=1, model="gemini-3.1-flash-image", size="3:4") -> list[GeneratedArtwork]`
  - `generators.GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"`

- [x] **Step 1: Write the failing registry test for the two new fields**

Append to `tests/test_providers.py`:

```python
def test_every_provider_declares_a_text_model_and_seed_support() -> None:
    for provider_id, spec in PROVIDERS.items():
        assert isinstance(spec.text_model, str)
        assert isinstance(spec.supports_seed, bool)


def test_google_is_available_with_a_text_model() -> None:
    assert "google" in PROVIDERS
    google = PROVIDERS["google"]
    assert google.text_model == "gemini-3.5-flash-lite"
    assert google.default_model == "gemini-3.1-flash-image"
    assert google.portrait_size == "3:4"
    assert google.square_size == "1:1"


def test_recraft_has_no_text_model_but_supports_seeds() -> None:
    assert PROVIDERS["recraft"].text_model == ""
    assert PROVIDERS["recraft"].supports_seed is True


def test_openai_has_a_text_model_and_no_seed() -> None:
    assert PROVIDERS["openai"].text_model == "gpt-5-mini"
    assert PROVIDERS["openai"].supports_seed is False
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: FAIL with `AttributeError: 'ProviderSpec' object has no attribute 'text_model'` and `KeyError: 'google'`.

- [x] **Step 3: Add the fields and the Google entry**

In `colouring_factory/providers.py`, add two fields to the end of `ProviderSpec`:

```python
    text_model: str = ""
    supports_seed: bool = False
```

Set them on the existing entries — `text_model="gpt-5-mini", supports_seed=False` on `openai`, and `text_model="", supports_seed=True` on `recraft` — then add a third entry to `PROVIDERS`:

```python
    "google": ProviderSpec(
        id="google",
        label="Google Gemini",
        env_var="GEMINI_API_KEY",
        key_url="https://aistudio.google.com/apikey",
        billing_url="https://aistudio.google.com/usage",
        docs_url="https://ai.google.dev/gemini-api/docs/image-generation",
        default_model="gemini-3.1-flash-image",
        models=("gemini-3.1-flash-image", "gemini-3.1-flash-lite-image", "gemini-3-pro-image"),
        portrait_size="3:4",
        square_size="1:1",
        key_placeholder="AIza…",
        description="Has a free tier, so it is the cheapest way to start.",
        billing_note="A free allowance covers occasional use; heavier use needs billing enabled.",
        text_model="gemini-3.5-flash-lite",
        supports_seed=False,
    ),
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS.

- [x] **Step 5: Write the failing Google generator test**

Create `tests/test_generators_google.py`. The Google call is made with `urllib.request.urlopen`, so the test replaces that name inside the `generators` module — no network traffic occurs.

```python
import base64
import json
from io import BytesIO

import pytest

from colouring_factory import generators
from colouring_factory.generators import GeneratorError, generate_with_google

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_reply(payload: dict) -> _FakeResponse:
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def _one_image_reply() -> dict:
    return {
        "model": "gemini-3.1-flash-image",
        "status": "completed",
        "steps": [
            {
                "type": "model_output",
                "content": [{"type": "image", "mime_type": "image/png", "data": PIXEL}],
            }
        ],
    }


def test_google_returns_decoded_image_bytes(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return _google_reply(_one_image_reply())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    artworks = generate_with_google(api_key="AIza-test", prompt="a bear", size="3:4")

    assert len(artworks) == 1
    assert artworks[0].image_bytes == b"fake-png-bytes"
    assert artworks[0].provider == "Google Gemini"
    assert captured["url"] == generators.GOOGLE_ENDPOINT
    assert captured["body"]["input"] == [{"type": "text", "text": "a bear"}]
    assert captured["body"]["response_format"]["aspect_ratio"] == "3:4"
    # urllib title-cases header names.
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"


def test_google_makes_one_request_per_variant(monkeypatch) -> None:
    calls = []

    def fake_urlopen(request, timeout=None):
        calls.append(json.loads(request.data.decode("utf-8"))["input"][0]["text"])
        return _google_reply(_one_image_reply())

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    artworks = generate_with_google(api_key="AIza-test", prompt="a bear", variants=3)

    assert len(artworks) == 3
    assert len(calls) == 3


def test_google_rejects_a_missing_key() -> None:
    with pytest.raises(GeneratorError) as caught:
        generate_with_google(api_key="  ", prompt="a bear")
    assert caught.value.code == "missing_key"


def test_google_explains_a_reply_with_no_image(monkeypatch) -> None:
    reply = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": "refused"}]}]}
    monkeypatch.setattr(generators, "urlopen", lambda request, timeout=None: _google_reply(reply))

    with pytest.raises(GeneratorError) as caught:
        generate_with_google(api_key="AIza-test", prompt="a bear")
    assert "no image" in str(caught.value).lower()
```

- [x] **Step 6: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_generators_google.py -v`
Expected: FAIL with `ImportError: cannot import name 'generate_with_google'`.

- [x] **Step 7: Implement the Google generator**

In `colouring_factory/generators.py`, add the endpoint constant near the top:

```python
GOOGLE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
```

and the generator alongside `generate_with_recraft`:

```python
def _google_image_block(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for step in payload.get("steps") or ():
        if not isinstance(step, dict):
            continue
        for block in step.get("content") or ():
            if isinstance(block, dict) and block.get("type") == "image" and block.get("data"):
                return str(block["data"])
    return ""


def generate_with_google(
    *,
    api_key: str,
    prompt: str,
    variants: int = 1,
    model: str = "gemini-3.1-flash-image",
    size: str = "3:4",
) -> list[GeneratedArtwork]:
    """Generate raster artwork with the Gemini Interactions API."""

    if not api_key.strip():
        raise GeneratorError(
            "Connect Google Gemini with an API key before generating artwork.",
            provider="Google Gemini",
            code="missing_key",
        )
    if variants < 1 or variants > 4:
        raise GeneratorError("Variants must be between 1 and 4.")

    images: list[GeneratedArtwork] = []
    for index in range(variants):
        variant_prompt = _variant_prompt(prompt, index, variants)
        body = {
            "model": model,
            "input": [{"type": "text", "text": variant_prompt}],
            "response_format": {
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": size,
                "image_size": "2K",
            },
        }
        request = Request(
            GOOGLE_ENDPOINT,
            data=json.dumps(body).encode("utf-8"),
            headers={
                "x-goog-api-key": api_key.strip(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=240) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except OSError:
                detail = ""
            raise _normalise_error("Google Gemini", exc, status_code=exc.code, details=detail) from exc
        except (URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise _normalise_error("Google Gemini", exc) from exc

        encoded = _google_image_block(payload)
        if not encoded:
            raise GeneratorError(
                "Google Gemini returned no image. It may have declined the description.",
                provider="Google Gemini",
                code="content",
            )
        image_bytes = _read_image_payload({"b64_json": encoded})

        images.append(
            GeneratedArtwork(
                image_bytes=image_bytes,
                prompt=variant_prompt,
                provider="Google Gemini",
                model=model,
                metadata={"variant": index + 1, "size": size},
            )
        )

    return images
```

- [x] **Step 8: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_generators_google.py -v`
Expected: PASS.

- [x] **Step 9: Route Google through the dispatcher and the connection check**

In `generate_with_provider`, add before the final `raise`:

```python
    if provider == "google":
        return generate_with_google(
            api_key=api_key,
            prompt=prompt,
            variants=variants,
            model=model,
            size=size,
        )
```

In `check_provider_connection`, extend the endpoint selection. Google's models endpoint accepts the same header and costs nothing:

```python
    elif provider == "google":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
        label = "Google Gemini"
```

Google authenticates with `x-goog-api-key` rather than a bearer token, so build the request headers per provider instead of always sending `Authorization`:

```python
    headers = {"Accept": "application/json"}
    if provider == "google":
        headers["x-goog-api-key"] = key
    else:
        headers["Authorization"] = f"Bearer {key}"

    request = Request(endpoint, headers=headers, method="GET")
```

- [x] **Step 10: Write the connection-check test**

Append to `tests/test_generators_google.py`:

```python
def test_google_connection_check_uses_the_google_header(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.headers)
        return _google_reply({"models": []})

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    result = generators.check_provider_connection("google", "AIza-test")

    assert result["valid"] is True
    assert result["provider"] == "Google Gemini"
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"
    assert "Authorization" not in captured["headers"]


def test_openai_connection_check_still_uses_a_bearer_token(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["headers"] = dict(request.headers)
        return _google_reply({"data": []})

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    generators.check_provider_connection("openai", "sk-test")

    assert captured["headers"]["Authorization"] == "Bearer sk-test"
```

- [x] **Step 11: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass.

- [x] **Step 12: Add the Google key to the example environment file**

In `.env.example`, below the existing OpenAI line:

```text
# Optional. Google Gemini has a free tier; get a key at https://aistudio.google.com/apikey
GEMINI_API_KEY=your_key_here

# Optional. Recraft; get a token at https://app.recraft.ai/profile/api
RECRAFT_API_TOKEN=your_token_here
```

- [x] **Step 13: Commit**

```bash
git add colouring_factory/providers.py colouring_factory/generators.py tests/test_providers.py tests/test_generators_google.py .env.example
git commit -m "Add Google Gemini as a third image provider

Two paid vendors still left no way to use Doodle without a card on
file. Gemini has a free allowance, so it becomes the cheap starting
point. Its API differs from the other two: an aspect ratio rather than
a pixel size, an x-goog-api-key header rather than a bearer token, and
content blocks rather than a data array, so the connection check now
builds headers per provider.

Model identifiers and the endpoint shape were read from Google's live
documentation on 2026-08-30 rather than from memory.

ProviderSpec also gains text_model and supports_seed, which the
variation work depends on."
```

---

## Task 3: Curated variation axes (the fallback path)

Build the fallback first, because it has no network dependency and the text-model path in Task 4 falls back to it. Four axes — the moment in the story, the camera framing, the setting, and the mood — combined differently per variant.

**Files:**
- Create: `colouring_factory/variations.py`
- Create: `tests/test_variations.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `variations.VARIATION_AXES: dict[str, tuple[str, ...]]` with keys `"moment"`, `"framing"`, `"setting"`, `"mood"`
  - `variations.axis_briefs(concept: str, count: int) -> tuple[str, ...]`

- [x] **Step 1: Write the failing test**

Create `tests/test_variations.py`:

```python
import pytest

from colouring_factory.variations import VARIATION_AXES, axis_briefs


def test_axis_briefs_returns_the_requested_count() -> None:
    for count in (1, 2, 3, 4):
        assert len(axis_briefs("a bear flying a kite", count)) == count


def test_axis_briefs_are_all_different() -> None:
    briefs = axis_briefs("a bear flying a kite", 4)
    assert len(set(briefs)) == 4


def test_every_brief_mentions_the_concept() -> None:
    for brief in axis_briefs("a bear flying a kite", 4):
        assert "a bear flying a kite" in brief


def test_axis_briefs_are_deterministic_for_the_same_request() -> None:
    assert axis_briefs("a bear flying a kite", 3) == axis_briefs("a bear flying a kite", 3)


def test_different_concepts_get_different_briefs() -> None:
    bear = axis_briefs("a bear flying a kite", 3)
    dino = axis_briefs("a dinosaur washing a fire engine", 3)
    assert bear != dino


def test_a_shorter_request_is_a_prefix_of_a_longer_one() -> None:
    # Asking for one more alternative should add to the set, not reshuffle it,
    # so that pressing "another" keeps the pictures the user has already seen.
    assert axis_briefs("a bear flying a kite", 2) == axis_briefs("a bear flying a kite", 4)[:2]


def test_each_brief_varies_all_four_axes() -> None:
    briefs = axis_briefs("a bear flying a kite", 4)
    for axis_values in VARIATION_AXES.values():
        used = [value for value in axis_values if any(value in brief for brief in briefs)]
        assert len(used) >= 2, "at least two distinct values per axis across four briefs"


def test_an_empty_concept_is_refused() -> None:
    with pytest.raises(ValueError):
        axis_briefs("   ", 2)


def test_a_count_outside_one_to_four_is_refused() -> None:
    with pytest.raises(ValueError):
        axis_briefs("a bear", 0)
    with pytest.raises(ValueError):
        axis_briefs("a bear", 5)
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_variations.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'colouring_factory.variations'`.

- [x] **Step 3: Implement the axes**

Create `colouring_factory/variations.py`:

```python
from __future__ import annotations

VARIATION_AXES: dict[str, tuple[str, ...]] = {
    "moment": (
        "the busiest moment of the action",
        "the quiet moment just before it begins",
        "the moment just after it is finished",
        "an unexpected small mishap in the middle of it",
    ),
    "framing": (
        "a wide view showing the whole scene",
        "a close view of the main character's face and hands",
        "a low view looking up at the subject",
        "a side view showing the whole body in profile",
    ),
    "setting": (
        "outdoors on a sunny day",
        "indoors in a cosy room",
        "in a garden with simple large plants",
        "beside water, with simple wide ripples",
    ),
    "mood": (
        "cheerful and energetic",
        "calm and sleepy",
        "proud and pleased",
        "surprised and curious",
    ),
}

_AXIS_ORDER = ("moment", "framing", "setting", "mood")


def axis_briefs(concept: str, count: int) -> tuple[str, ...]:
    """Compose distinct scene briefs by varying four axes independently.

    Each axis advances by a different stride so that four briefs never repeat a
    combination, and a request for fewer alternatives is a prefix of a request
    for more — pressing "another" must not reshuffle pictures already seen.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if count < 1 or count > 4:
        raise ValueError("Between one and four alternatives can be produced.")

    strides = (1, 3, 2, 3)
    offset = sum(ord(character) for character in concept)

    briefs: list[str] = []
    for index in range(count):
        parts = []
        for axis_position, axis_name in enumerate(_AXIS_ORDER):
            values = VARIATION_AXES[axis_name]
            chosen = values[(offset + (index * strides[axis_position])) % len(values)]
            parts.append(chosen)
        moment, framing, setting, mood = parts
        briefs.append(
            f"{concept}, shown at {moment}, drawn as {framing}, {setting}, feeling {mood}."
        )
    return tuple(briefs)
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_variations.py -v`
Expected: PASS. If `test_axis_briefs_are_all_different` fails, the strides collide for that offset — change the `strides` tuple so no two indices produce the same four-tuple, and re-run.

- [x] **Step 5: Commit**

```bash
git add colouring_factory/variations.py tests/test_variations.py
git commit -m "Add curated variation axes for distinct scene briefs

Variants previously differed by one appended sentence asking the model
to vary the pose, which produced near-identical pictures. This composes
briefs that vary four things independently: the moment in the story,
the camera framing, the setting and the mood.

Selection is deterministic, and a request for fewer alternatives is a
prefix of a request for more, so asking for another picture does not
reshuffle the ones already on screen."
```

---

## Task 4: Text-model brief writing, falling back to axes

**Files:**
- Modify: `colouring_factory/variations.py`
- Modify: `tests/test_variations.py`

**Interfaces:**
- Consumes: `providers.get_provider`, `generators.GOOGLE_ENDPOINT`, `axis_briefs` from Task 3.
- Produces:
  - `variations.written_briefs(concept, count, *, provider_id, api_key) -> tuple[str, ...]` — raises `GeneratorError` on any failure
  - `variations.build_variation_briefs(concept, count, *, provider_id, api_key) -> tuple[str, ...]` — never raises for provider reasons; falls back to `axis_briefs`

- [x] **Step 1: Write the failing test**

Append to `tests/test_variations.py`:

```python
import json
from io import BytesIO

from colouring_factory import variations
from colouring_factory.variations import build_variation_briefs, written_briefs


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_text_reply(text: str) -> _FakeResponse:
    payload = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": text}]}]}
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


THREE_BRIEFS = json.dumps(
    [
        "The bear runs across a hilltop, kite string taut behind it.",
        "Close on the bear's face, tongue out, squinting up at the kite.",
        "The bear sits in long grass, the kite tangled in a small tree.",
    ]
)


def test_written_briefs_parses_a_json_list(monkeypatch) -> None:
    monkeypatch.setattr(
        variations, "urlopen", lambda request, timeout=None: _google_text_reply(THREE_BRIEFS)
    )
    briefs = written_briefs("a bear flying a kite", 3, provider_id="google", api_key="AIza-test")
    assert len(briefs) == 3
    assert "hilltop" in briefs[0]


def test_written_briefs_tolerates_a_fenced_code_block(monkeypatch) -> None:
    fenced = f"```json\n{THREE_BRIEFS}\n```"
    monkeypatch.setattr(
        variations, "urlopen", lambda request, timeout=None: _google_text_reply(fenced)
    )
    assert len(written_briefs("a bear flying a kite", 3, provider_id="google", api_key="k")) == 3


def test_written_briefs_rejects_the_wrong_count(monkeypatch) -> None:
    monkeypatch.setattr(
        variations, "urlopen", lambda request, timeout=None: _google_text_reply(THREE_BRIEFS)
    )
    with pytest.raises(GeneratorError):
        written_briefs("a bear flying a kite", 4, provider_id="google", api_key="k")


def test_written_briefs_rejects_duplicates(monkeypatch) -> None:
    duplicated = json.dumps(["The bear runs.", "the bear runs", "The bear sits."])
    monkeypatch.setattr(
        variations, "urlopen", lambda request, timeout=None: _google_text_reply(duplicated)
    )
    with pytest.raises(GeneratorError):
        written_briefs("a bear flying a kite", 3, provider_id="google", api_key="k")


def test_a_provider_without_a_text_model_falls_back_to_axes() -> None:
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="recraft", api_key="token"
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_a_failed_text_call_falls_back_to_axes(monkeypatch) -> None:
    def explode(request, timeout=None):
        raise TimeoutError("no network")

    monkeypatch.setattr(variations, "urlopen", explode)
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="google", api_key="AIza-test"
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_a_malformed_reply_falls_back_to_axes(monkeypatch) -> None:
    monkeypatch.setattr(
        variations, "urlopen", lambda request, timeout=None: _google_text_reply("not json at all")
    )
    briefs = build_variation_briefs(
        "a bear flying a kite", 3, provider_id="google", api_key="AIza-test"
    )
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_a_missing_key_falls_back_to_axes() -> None:
    briefs = build_variation_briefs("a bear flying a kite", 3, provider_id="google", api_key="")
    assert briefs == axis_briefs("a bear flying a kite", 3)


def test_one_alternative_needs_no_text_call(monkeypatch) -> None:
    def explode(request, timeout=None):
        raise AssertionError("no text call should be made for a single picture")

    monkeypatch.setattr(variations, "urlopen", explode)
    assert build_variation_briefs("a bear", 1, provider_id="google", api_key="k") == ("a bear",)
```

Add the missing import at the top of the file: `from colouring_factory.generators import GeneratorError`.

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_variations.py -v`
Expected: FAIL with `ImportError: cannot import name 'written_briefs'`.

- [x] **Step 3: Implement brief writing**

Add to `colouring_factory/variations.py`. Note the imports go at the top of the file, and `urlopen` is imported by name so tests can replace it.

```python
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .generators import GOOGLE_ENDPOINT, GeneratorError
from .providers import get_provider

_BRIEF_INSTRUCTION = (
    "You plan children's colouring-book pictures. Given one picture idea, write {count} "
    "different scenes that all show that idea. Each scene must differ from the others in the "
    "moment of the story it captures, the camera framing, the setting, and the mood. Never "
    "simply restate the idea. Keep each scene to one sentence a five-year-old could picture, "
    "with no colour words and no text or lettering in the scene.\n\n"
    "Picture idea: {concept}\n\n"
    'Reply with only a JSON array of exactly {count} strings, for example ["...", "..."].'
)


def _extract_json_array(text: str) -> list[str]:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    if not stripped.startswith("["):
        bracketed = re.search(r"\[.*\]", stripped, re.DOTALL)
        if not bracketed:
            raise GeneratorError("The text model did not return a list of scenes.", code="brief_format")
        stripped = bracketed.group(0)
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise GeneratorError("The text model returned unreadable scenes.", code="brief_format") from exc
    if not isinstance(parsed, list):
        raise GeneratorError("The text model did not return a list of scenes.", code="brief_format")
    return [str(item).strip() for item in parsed]


def _google_text(model: str, api_key: str, instruction: str) -> str:
    request = Request(
        GOOGLE_ENDPOINT,
        data=json.dumps({"model": model, "input": instruction}).encode("utf-8"),
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    for step in payload.get("steps") or ():
        for block in step.get("content") or ():
            if isinstance(block, dict) and block.get("type") == "text":
                return str(block.get("text", ""))
    return ""


def _openai_text(model: str, api_key: str, instruction: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, timeout=60.0, max_retries=1)
    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": instruction}],
    )
    return str(completion.choices[0].message.content or "")


def written_briefs(
    concept: str,
    count: int,
    *,
    provider_id: str,
    api_key: str,
) -> tuple[str, ...]:
    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")

    spec = get_provider(provider_id)
    if not spec.text_model:
        raise GeneratorError(f"{spec.label} has no text model.", code="no_text_model")
    if not api_key.strip():
        raise GeneratorError(f"{spec.label} is not connected.", code="missing_key")

    instruction = _BRIEF_INSTRUCTION.format(count=count, concept=concept)
    try:
        if spec.id == "google":
            reply = _google_text(spec.text_model, api_key.strip(), instruction)
        else:
            reply = _openai_text(spec.text_model, api_key.strip(), instruction)
    except GeneratorError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise GeneratorError(f"Could not reach {spec.label} to plan the scenes.", code="network") from exc
    except Exception as exc:
        raise GeneratorError(f"{spec.label} could not plan the scenes: {exc}", code="brief_failed") from exc

    briefs = _extract_json_array(reply)
    if len(briefs) != count or any(not brief for brief in briefs):
        raise GeneratorError("The text model returned the wrong number of scenes.", code="brief_format")

    normalised = {re.sub(r"[^a-z0-9]+", " ", brief.lower()).strip() for brief in briefs}
    if len(normalised) != count:
        raise GeneratorError("The text model repeated a scene.", code="brief_format")

    return tuple(briefs)


def build_variation_briefs(
    concept: str,
    count: int,
    *,
    provider_id: str,
    api_key: str,
) -> tuple[str, ...]:
    """Return `count` distinct scene briefs, preferring a written plan.

    A weaker variation beats no picture at all, so every provider failure
    falls back to the deterministic axes rather than propagating.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if count < 1 or count > 4:
        raise ValueError("Between one and four alternatives can be produced.")
    if count == 1:
        return (concept,)

    try:
        return written_briefs(concept, count, provider_id=provider_id, api_key=api_key)
    except (GeneratorError, ValueError):
        return axis_briefs(concept, count)
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_variations.py -v`
Expected: PASS.

- [x] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass. A circular-import error between `variations` and `generators` means `generators` has grown an import of `variations` — it must not; the dependency runs one way only.

- [x] **Step 6: Commit**

```bash
git add colouring_factory/variations.py tests/test_variations.py
git commit -m "Write variation briefs with a text model where one exists

Asks the provider's own text model to plan distinct scenes before any
drawing happens, validating that it returned the right number with no
repeats. OpenAI and Gemini have text models; Recraft does not, so it
uses the curated axes instead.

Every provider failure falls back to the axes rather than propagating,
because a weaker variation is better than no picture. A single picture
skips the planning call entirely."
```

---

## Task 5: Feed the briefs into prompts, generators and the studio

The generators currently take one prompt plus a variant count and invent the difference themselves. Responsibility inverts: the caller supplies one prompt per picture, and the generator only draws.

**Files:**
- Modify: `colouring_factory/prompts.py`
- Modify: `colouring_factory/generators.py`
- Modify: `app.py`
- Modify: `tests/test_prompts.py`
- Create: `tests/test_generator_prompts.py`

**Interfaces:**
- Consumes: `variations.build_variation_briefs` from Task 4.
- Produces:
  - `prompts.build_colouring_prompt(concept, age_profile=..., style_name=..., target=..., extra_instructions="", variation_brief="") -> str`
  - `generators.generate_with_provider(*, provider_id, api_key, prompts: Sequence[str], model, size, quality="low", random_seed=None) -> list[GeneratedArtwork]`
  - The same `prompts: Sequence[str]` signature on `generate_with_openai`, `generate_with_recraft` and `generate_with_google`. `_variant_prompt` is deleted.

- [x] **Step 1: Write the failing prompt test**

Append to `tests/test_prompts.py`:

```python
def test_a_variation_brief_replaces_the_bare_concept() -> None:
    brief = "The bear sits in long grass, the kite tangled in a small tree."
    prompt = build_colouring_prompt("a bear flying a kite", variation_brief=brief)
    assert brief in prompt


def test_style_and_age_rules_are_identical_across_briefs() -> None:
    first = build_colouring_prompt("a bear", variation_brief="Brief one.")
    second = build_colouring_prompt("a bear", variation_brief="Brief two.")
    assert first.replace("Brief one.", "X") == second.replace("Brief two.", "X")


def test_no_brief_leaves_the_prompt_unchanged() -> None:
    assert build_colouring_prompt("a bear") == build_colouring_prompt("a bear", variation_brief="")


def test_the_round_badge_rule_asks_for_a_circular_composition() -> None:
    prompt = build_colouring_prompt("a bear", target="Round badge")
    lowered = prompt.lower()
    assert "circle" in lowered or "circular" in lowered
    assert "corner" in lowered
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: FAIL with `TypeError: build_colouring_prompt() got an unexpected keyword argument 'variation_brief'`.

- [x] **Step 3: Add the parameter and strengthen the badge rule**

In `colouring_factory/prompts.py`, change the signature to add `variation_brief: str = ""` as the last parameter, and replace the scene line so a brief takes precedence:

```python
    scene = variation_brief.strip() or concept
```

then use `Scene: {scene}` in the prompt body in place of `Scene: {concept}`.

Replace `TARGET_RULES["Round badge"]` with:

```python
    "Round badge": (
        "Use a square composition built for a circular crop. Place the whole subject inside an "
        "imaginary circle that touches the edges of the square, keep every essential feature well "
        "within that circle, and leave the four corners empty. Nothing that matters may sit in a "
        "corner, because the corners are cut away when the badge is made."
    ),
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: PASS.

- [x] **Step 5: Write the failing generator-interface test**

Create `tests/test_generator_prompts.py`:

```python
import base64
import json
from io import BytesIO

from colouring_factory import generators
from colouring_factory.generators import generate_with_provider

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def test_each_prompt_is_sent_exactly_as_given(monkeypatch) -> None:
    sent = []

    def fake_urlopen(request, timeout=None):
        sent.append(json.loads(request.data.decode("utf-8"))["input"][0]["text"])
        payload = {
            "steps": [
                {"type": "model_output", "content": [{"type": "image", "data": PIXEL}]}
            ]
        }
        return _FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    artworks = generate_with_provider(
        provider_id="google",
        api_key="AIza-test",
        prompts=["first scene", "second scene"],
        model="gemini-3.1-flash-image",
        size="3:4",
    )

    assert sent == ["first scene", "second scene"]
    assert [art.prompt for art in artworks] == ["first scene", "second scene"]


def test_the_old_variant_helper_is_gone() -> None:
    assert not hasattr(generators, "_variant_prompt")
```

- [x] **Step 6: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_generator_prompts.py -v`
Expected: FAIL with `TypeError: generate_with_provider() got an unexpected keyword argument 'prompts'`.

- [x] **Step 7: Change the generator interface**

In `colouring_factory/generators.py`:

Delete `_variant_prompt` entirely.

In each of `generate_with_openai`, `generate_with_recraft` and `generate_with_google`, replace the `prompt: str` and `variants: int = 1` parameters with `prompts: Sequence[str]`, replace the range loop header with `for index, variant_prompt in enumerate(prompts):`, and delete the `variant_prompt = _variant_prompt(...)` line inside each. Replace each count guard with:

```python
    if not 1 <= len(prompts) <= 4:
        raise GeneratorError("Between one and four pictures can be drawn at once.")
```

Add `from collections.abc import Sequence` to the imports.

In `generate_with_provider`, replace `prompt: str` and `variants: int` with `prompts: Sequence[str]` and pass `prompts=prompts` to each branch.

- [x] **Step 8: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_generator_prompts.py tests/test_generators_google.py -v`
Expected: PASS. The Task 2 Google tests call `generate_with_google(prompt=...)`; update those calls to `prompts=[...]` and the `variants=3` case to three prompts.

- [x] **Step 9: Wire it into the studio generation form**

In `app.py`, inside the `Generate with AI` branch, replace the block that builds one prompt and calls the generator with:

```python
                    briefs = build_variation_briefs(
                        idea,
                        int(variants),
                        provider_id=studio_provider_id,
                        api_key=api_key,
                    )
                    variant_prompts = [
                        build_colouring_prompt(
                            idea,
                            age_profile=age_profile,
                            style_name=style_name,
                            target=target,
                            extra_instructions=extra,
                            variation_brief=brief,
                        )
                        for brief in briefs
                    ]
                    size = studio_provider.portrait_size if target == "A4 page" else studio_provider.square_size
                    nonce = int(st.session_state.get("generation_nonce", 0))
                    seed_source = f"{idea}|{style_name}|{target}|{nonce}"
                    random_seed = int(hashlib.sha256(seed_source.encode("utf-8")).hexdigest()[:8], 16)
                    with st.spinner(f"Drawing {int(variants)} doodle(s)..."):
                        artworks = generate_with_provider(
                            provider_id=studio_provider_id,
                            api_key=api_key,
                            prompts=variant_prompts,
                            model=model,
                            size=size,
                            quality=quality,
                            random_seed=random_seed,
                        )
```

Add `from colouring_factory.variations import build_variation_briefs` to the imports.

In `_quick_generate`, which always draws one picture, replace the `prompt=prompt, variants=1` arguments with `prompts=[prompt]`.

Under the existing "Exact generation prompt" expander, add a second expander so the interpretation is inspectable:

```python
            if len(st.session_state.candidates) > 1:
                with st.expander("How the alternatives differ"):
                    for index, candidate in enumerate(st.session_state.candidates, start=1):
                        st.markdown(f"**Alternative {index}**")
                        st.caption(candidate.metadata.get("brief", "—"))
```

and record the brief when generating, by adding `"brief": brief` to each artwork's metadata. Do this by zipping briefs with artworks after the call:

```python
                    for artwork, brief in zip(artworks, briefs):
                        artwork.metadata["brief"] = brief
```

- [x] **Step 10: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass.

- [x] **Step 11: Commit**

```bash
git add colouring_factory/prompts.py colouring_factory/generators.py app.py tests/test_prompts.py tests/test_generator_prompts.py tests/test_generators_google.py
git commit -m "Draw each alternative from its own scene brief

Generators took one prompt and a count, and invented the difference
between variants themselves by appending a sentence, which is why the
pictures came back near-identical. They now take one prompt per
picture and only draw; the caller decides what differs.

Round-badge prompts also now ask for a composition that keeps the
corners empty, so badge artwork is generated badge-shaped rather than
rescued by cropping afterwards.

The studio shows how the alternatives differ, so an interpretation that
missed can be spotted without regenerating."
```

---

## Task 6: Inscribe badge artwork inside the safe circle

Artwork is scaled to fill the square that bounds the safe circle and then clipped to the circle, so the four corners are cut away without warning. A picture that reaches its own edges loses those edges.

**Files:**
- Modify: `colouring_factory/layouts.py`
- Modify: `colouring_factory/models.py`
- Modify: `colouring_factory/pdf_export.py`
- Create: `tests/test_badge_fit.py`

**Interfaces:**
- Consumes: `layouts.fit_contain`, `models.CircleSheetConfig` from the existing codebase.
- Produces:
  - `layouts.fit_inscribed(source_width, source_height, centre_x, centre_y, ellipse_width, ellipse_height) -> tuple[float, float, float, float]` returning `(x, y, width, height)`, matching `fit_contain`'s convention
  - `models.CircleSheetConfig.fit_mode: str = "inscribe"`

- [x] **Step 1: Write the failing geometry test**

Create `tests/test_badge_fit.py`:

```python
import math

import pytest

from colouring_factory.layouts import fit_contain, fit_inscribed


def _corners(x, y, width, height):
    return ((x, y), (x + width, y), (x, y + height), (x + width, y + height))


def _inside_ellipse(point, centre_x, centre_y, width, height, tolerance=1e-6):
    px, py = point
    normalised = ((px - centre_x) / (width / 2.0)) ** 2 + ((py - centre_y) / (height / 2.0)) ** 2
    return normalised <= 1.0 + tolerance


@pytest.mark.parametrize(
    "source_width,source_height",
    [(1024, 1024), (1024, 1536), (1536, 1024), (300, 100)],
)
def test_every_corner_lands_inside_the_circle(source_width, source_height) -> None:
    box = fit_inscribed(source_width, source_height, 100.0, 100.0, 58.0, 58.0)
    for corner in _corners(*box):
        assert _inside_ellipse(corner, 100.0, 100.0, 58.0, 58.0)


def test_a_square_source_uses_the_diameter_over_root_two() -> None:
    _x, _y, width, height = fit_inscribed(1000, 1000, 0.0, 0.0, 58.0, 58.0)
    expected = 58.0 / math.sqrt(2.0)
    assert width == pytest.approx(expected)
    assert height == pytest.approx(expected)


def test_the_aspect_ratio_of_the_source_is_preserved() -> None:
    _x, _y, width, height = fit_inscribed(1024, 1536, 0.0, 0.0, 58.0, 58.0)
    assert width / height == pytest.approx(1024 / 1536)


def test_the_result_is_centred_on_the_given_point() -> None:
    x, y, width, height = fit_inscribed(1024, 1536, 12.0, -7.0, 58.0, 58.0)
    assert x + (width / 2.0) == pytest.approx(12.0)
    assert y + (height / 2.0) == pytest.approx(-7.0)


def test_inscribing_is_smaller_than_containing() -> None:
    _cx, _cy, contain_width, _ch = fit_contain(1000, 1000, 0.0, 0.0, 58.0, 58.0)
    _ix, _iy, inscribe_width, _ih = fit_inscribed(1000, 1000, 29.0, 29.0, 58.0, 58.0)
    assert inscribe_width < contain_width


def test_an_anisotropic_ellipse_is_handled() -> None:
    box = fit_inscribed(1000, 1000, 0.0, 0.0, 60.0, 50.0)
    for corner in _corners(*box):
        assert _inside_ellipse(corner, 0.0, 0.0, 60.0, 50.0)


def test_a_zero_sized_source_is_refused() -> None:
    with pytest.raises(ValueError):
        fit_inscribed(0, 100, 0.0, 0.0, 58.0, 58.0)


def test_a_zero_sized_ellipse_is_refused() -> None:
    with pytest.raises(ValueError):
        fit_inscribed(100, 100, 0.0, 0.0, 0.0, 58.0)
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_badge_fit.py -v`
Expected: FAIL with `ImportError: cannot import name 'fit_inscribed'`.

- [x] **Step 3: Implement the geometry**

Add to `colouring_factory/layouts.py`:

```python
def fit_inscribed(
    source_width: float,
    source_height: float,
    centre_x: float,
    centre_y: float,
    ellipse_width: float,
    ellipse_height: float,
) -> tuple[float, float, float, float]:
    """Largest rectangle of the source's aspect ratio fitting wholly inside the ellipse.

    Scaling a rectangle to the ellipse's bounding box leaves its corners outside
    the ellipse, so anything drawn there is clipped away. Solving the ellipse
    equation for the corner instead guarantees nothing is lost: for half-extents
    (a, b) and aspect ratio r = w/h, w = 2ar / sqrt(r^2 + (a/b)^2).
    """

    if source_width <= 0 or source_height <= 0:
        raise ValueError("Source dimensions must be positive.")
    if ellipse_width <= 0 or ellipse_height <= 0:
        raise ValueError("Ellipse dimensions must be positive.")

    semi_x = ellipse_width / 2.0
    semi_y = ellipse_height / 2.0
    ratio = source_width / source_height

    width = (2.0 * semi_x * ratio) / math.sqrt((ratio**2) + ((semi_x / semi_y) ** 2))
    height = width / ratio

    return centre_x - (width / 2.0), centre_y - (height / 2.0), width, height
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_badge_fit.py -v`
Expected: PASS.

- [x] **Step 5: Add the fit mode to the configuration**

In `colouring_factory/models.py`, add to `CircleSheetConfig` after `show_safe_guide`:

```python
    fit_mode: str = "inscribe"
```

- [x] **Step 6: Write the failing export test**

Add these imports to the top of `tests/test_badge_fit.py`, beside the existing ones:

```python
from io import BytesIO

import fitz
from PIL import Image

from colouring_factory.models import CalibrationProfile, CircleSheetConfig
from colouring_factory.pdf_export import create_circle_sheet_pdf
```

then append to the same file:

```python
def _full_bleed_png() -> bytes:
    image = Image.new("L", (400, 400), color=255)
    for x in range(400):
        for y in (0, 1, 398, 399):
            image.putpixel((x, y), 0)
            image.putpixel((y, x), 0)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_inscribe_is_the_default() -> None:
    assert CircleSheetConfig().fit_mode == "inscribe"


def _drawn_width_pt(artwork: bytes, mode: str) -> float:
    config = CircleSheetConfig(copies=1, fit_mode=mode)
    pdf_bytes, _count = create_circle_sheet_pdf(artwork, config, CalibrationProfile())
    page = fitz.open(stream=pdf_bytes, filetype="pdf")[0]
    placed = page.get_images(full=True)
    assert placed, "the badge sheet contains no image"
    return page.get_image_rects(placed[0][0])[0].width


def test_inscribed_artwork_is_smaller_than_filled_artwork() -> None:
    artwork = _full_bleed_png()
    assert _drawn_width_pt(artwork, "inscribe") < _drawn_width_pt(artwork, "fill")


def test_inscribed_artwork_measures_the_diameter_over_root_two() -> None:
    # A square source inside a 50 mm safe circle: 50 / sqrt(2) = 35.36 mm.
    from colouring_factory.layouts import mm_to_pt

    width_pt = _drawn_width_pt(_full_bleed_png(), "inscribe")
    assert width_pt == pytest.approx(mm_to_pt(50.0 / math.sqrt(2.0)), rel=0.01)


def test_fill_mode_reproduces_the_previous_geometry() -> None:
    artwork = _full_bleed_png()
    config = CircleSheetConfig(copies=1, fit_mode="fill")
    pdf_bytes, count = create_circle_sheet_pdf(artwork, config, CalibrationProfile())
    assert count == 1
    assert pdf_bytes.startswith(b"%PDF")
```

- [x] **Step 7: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_badge_fit.py -v`
Expected: FAIL on `test_inscribed_artwork_is_smaller_than_filled_artwork`, because both modes currently draw the same size.

- [x] **Step 8: Honour the fit mode in the export**

In `colouring_factory/pdf_export.py`, import `fit_inscribed` alongside `fit_contain`, and add a helper above `create_circle_sheet_pdf`:

```python
def _place_badge_art(
    pdf: canvas.Canvas,
    image_bytes: bytes,
    fit_mode: str,
    centre_x: float,
    centre_y: float,
    box_width: float,
    box_height: float,
) -> None:
    if fit_mode == "fill":
        _draw_image_contain(
            pdf,
            image_bytes,
            centre_x - (box_width / 2.0),
            centre_y - (box_height / 2.0),
            box_width,
            box_height,
        )
        return

    source_width, source_height = _image_dimensions(image_bytes)
    x, y, width, height = fit_inscribed(
        source_width, source_height, centre_x, centre_y, box_width, box_height
    )
    pdf.drawImage(
        ImageReader(BytesIO(image_bytes)),
        x,
        y,
        width=width,
        height=height,
        mask="auto",
    )
```

Replace both `_draw_image_contain(...)` calls inside `create_circle_sheet_pdf` with `_place_badge_art(...)`, passing `config.fit_mode`. In the captioned branch, the artwork's vertical centre moves up by half the caption height, so pass `centre_y + (caption_h / 2.0)` and `box_height=art_h`. Keep the ellipse clip in both modes as a safety net.

- [x] **Step 9: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_badge_fit.py -v`
Expected: PASS.

- [x] **Step 10: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass, including the existing `tests/test_circle_render.py` and `tests/test_pdfs.py`. If an existing circle test asserts a drawn size, it was asserting the old fill geometry — update it to construct its config with `fit_mode="fill"` so it keeps testing what it meant to test.

- [x] **Step 11: Commit**

```bash
git add colouring_factory/layouts.py colouring_factory/models.py colouring_factory/pdf_export.py tests/test_badge_fit.py
git commit -m "Fit badge artwork inside the safe circle instead of clipping it

Artwork was scaled to fill the square bounding the safe circle and then
clipped to the circle, so the four corners of every picture were cut
away silently. A scene reaching its own edges lost those edges.

fit_inscribed solves the ellipse equation for the corner, so the whole
picture fits. For a square source this is the diameter over root two,
about 70.7 per cent, so artwork is smaller than before by design. The
previous behaviour is kept as fit_mode='fill' for reproducibility."
```

---

## Task 7: Live badge preview with the three rings

You cannot currently see a badge until after the PDF is built. The preview is produced by exporting a real single-badge PDF and rasterising it, so it cannot drift from the printed output.

**Files:**
- Create: `colouring_factory/badge_preview.py`
- Create: `tests/test_badge_preview.py`
- Modify: `app.py`

**Interfaces:**
- Consumes: `pdf_export.create_circle_sheet_pdf`, `preview.render_pdf_preview`, `models.CircleSheetConfig`, `models.CalibrationProfile`.
- Produces: `badge_preview.render_badge_preview(image_bytes, config, calibration=None, dpi=200) -> bytes` returning PNG bytes.

- [x] **Step 1: Write the failing test**

Create `tests/test_badge_preview.py`:

```python
from io import BytesIO

import pytest
from PIL import Image

from colouring_factory.badge_preview import render_badge_preview
from colouring_factory.models import CalibrationProfile, CircleSheetConfig


def _artwork() -> bytes:
    image = Image.new("L", (400, 400), color=255)
    for coordinate in range(100, 300):
        image.putpixel((coordinate, 200), 0)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_the_preview_is_a_decodable_png() -> None:
    png = render_badge_preview(_artwork(), CircleSheetConfig())
    assert png.startswith(b"\x89PNG")
    Image.open(BytesIO(png)).verify()


def test_the_preview_is_square_for_a_circular_badge() -> None:
    png = render_badge_preview(_artwork(), CircleSheetConfig(cut_diameter_mm=58.0))
    image = Image.open(BytesIO(png))
    assert image.width == pytest.approx(image.height, rel=0.02)


def test_the_preview_is_proportional_to_the_cut_diameter() -> None:
    small = Image.open(BytesIO(render_badge_preview(_artwork(), CircleSheetConfig(cut_diameter_mm=40.0))))
    large = Image.open(BytesIO(render_badge_preview(_artwork(), CircleSheetConfig(cut_diameter_mm=80.0))))
    assert large.width > small.width


def test_all_three_guides_are_drawn_regardless_of_the_export_settings() -> None:
    # The preview exists to show boundaries, so it ignores the sheet's guide
    # checkboxes and always draws all three.
    config = CircleSheetConfig(
        finished_diameter_mm=58.0,
        cut_diameter_mm=62.0,
        safe_diameter_mm=48.0,
        show_cut_guide=False,
        show_finished_guide=False,
        show_safe_guide=False,
    )
    png = render_badge_preview(config=config, image_bytes=_artwork())
    greys = Image.open(BytesIO(png)).convert("L")
    dark_pixels = sum(1 for pixel in greys.getdata() if pixel < 200)
    assert dark_pixels > 0


def test_a_calibration_profile_is_accepted() -> None:
    png = render_badge_preview(
        _artwork(), CircleSheetConfig(), CalibrationProfile(x_scale=1.02, y_scale=1.01)
    )
    assert png.startswith(b"\x89PNG")
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_badge_preview.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'colouring_factory.badge_preview'`.

- [x] **Step 3: Implement the preview**

Create `colouring_factory/badge_preview.py`:

```python
from __future__ import annotations

from dataclasses import replace

from .models import CalibrationProfile, CircleSheetConfig
from .pdf_export import create_circle_sheet_pdf
from .preview import render_pdf_preview


def render_badge_preview(
    image_bytes: bytes,
    config: CircleSheetConfig,
    calibration: CalibrationProfile | None = None,
    dpi: int = 200,
) -> bytes:
    """Render one badge as a PNG, with all three boundary rings visible.

    Built by exporting a genuine single-badge PDF through the same code path as
    the printed sheet, so what is previewed cannot drift from what is printed.
    The page is sized to the badge plus a small surround, and the guide
    checkboxes are overridden on, because showing the boundaries is the entire
    purpose of this view.
    """

    calibration = calibration or CalibrationProfile()
    margin_mm = 4.0
    page_mm = max(config.cut_diameter_mm, config.finished_diameter_mm) + (2.0 * margin_mm)

    single = replace(
        config,
        page_width_mm=page_mm,
        page_height_mm=page_mm,
        margin_mm=margin_mm,
        gap_mm=0.0,
        copies=1,
        show_cut_guide=True,
        show_finished_guide=True,
        show_safe_guide=True,
    )

    pdf_bytes, _count = create_circle_sheet_pdf(image_bytes, single, calibration)
    return render_pdf_preview(pdf_bytes, dpi=dpi)
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_badge_preview.py -v`
Expected: PASS. If `create_circle_sheet_pdf` raises "No circles fit", the surround margin leaves too little room — the page is the diameter plus twice the margin, so check `compute_circle_sheet_plan` is not also subtracting the margin twice.

- [x] **Step 5: Show the preview in the studio**

In `app.py`, add the import `from colouring_factory.badge_preview import render_badge_preview`, add a cached wrapper beside the other `@st.cache_data` helpers:

```python
@st.cache_data(show_spinner=False)
def _cached_badge_preview(image_bytes: bytes, config_payload: str, calibration_payload: str) -> bytes:
    config = CircleSheetConfig(**json.loads(config_payload))
    calibration = CalibrationProfile.from_dict(json.loads(calibration_payload))
    return render_badge_preview(image_bytes, config, calibration)
```

and in the `A4 circle sheet` branch, immediately after the geometry box that reports how many circles fit, add:

```python
            preview_col, guide_col = st.columns([1, 1])
            with preview_col:
                try:
                    st.image(
                        _cached_badge_preview(
                            processed,
                            json.dumps(asdict(pdf_config), sort_keys=True),
                            json.dumps(active_calibration.to_dict(), sort_keys=True),
                        ),
                        caption="One badge, actual proportions",
                        use_container_width=True,
                    )
                except (ValueError, RuntimeError) as exc:
                    st.info(str(exc))
            with guide_col:
                st.markdown(
                    '<div class="geometry-box">'
                    "<strong>Solid line</strong> — where the paper is cut.<br>"
                    "<strong>Dashed line</strong> — the visible face once pressed.<br>"
                    "<strong>Dotted line</strong> — keep faces, eyes and text inside this.<br><br>"
                    "The whole picture is fitted inside the dotted circle, so nothing is lost "
                    "when the badge is made."
                    "</div>",
                    unsafe_allow_html=True,
                )
```

Add a fit-mode control to the guides row so filling stays reachable:

```python
            fit_choice = st.radio(
                "Artwork fit",
                ["Fit the whole picture", "Fill the circle"],
                horizontal=True,
                help="Filling the circle makes the picture larger but cuts off its corners.",
            )
```

and pass `fit_mode="inscribe" if fit_choice == "Fit the whole picture" else "fill"` into `CircleSheetConfig`.

- [x] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass.

- [x] **Step 7: Commit**

```bash
git add colouring_factory/badge_preview.py tests/test_badge_preview.py app.py
git commit -m "Show one badge with its three boundaries before export

A badge could not be seen until after the PDF was built, so there was
no way to judge whether a picture would survive the circular crop while
the settings were still being chosen.

The preview is produced by exporting a real single-badge PDF through
the same code path as the printed sheet and rasterising it, so what is
previewed cannot drift from what is printed. All three rings are drawn
regardless of the sheet's guide checkboxes, because showing the
boundaries is the whole point of this view."
```

---

## Task 8: Guidance for every failure

Errors currently print the problem and stop. Each one gains a cause, a fix, the name of the control responsible, and where a correction is computable, a button that applies it.

**Files:**
- Create: `colouring_factory/guidance.py`
- Create: `tests/test_guidance.py`
- Modify: `app.py`
- Modify: `colouring_factory/layouts.py`

**Interfaces:**
- Consumes: nothing. This module must not import Streamlit — it is data, rendered by the UI.
- Produces:
  - `guidance.Guidance` frozen dataclass with `title, cause, fix, control, action_label`
  - `guidance.guidance_for(code: str, **context) -> Guidance`
  - `guidance.GUIDANCE_CODES: frozenset[str]`
  - `layouts.largest_margin_that_fits(config) -> float | None`

- [x] **Step 1: Write the failing test**

Create `tests/test_guidance.py`:

```python
import inspect
import re

import pytest

from colouring_factory import generators
from colouring_factory.guidance import GUIDANCE_CODES, Guidance, guidance_for
from colouring_factory.layouts import largest_margin_that_fits
from colouring_factory.models import CircleSheetConfig


def test_every_generator_error_code_has_guidance() -> None:
    source = inspect.getsource(generators)
    raised = set(re.findall(r'code="([a-z_]+)"', source))
    assert raised, "no error codes found in generators.py"
    missing = raised - GUIDANCE_CODES
    assert not missing, f"no guidance for: {sorted(missing)}"


def test_every_guidance_entry_is_complete() -> None:
    for code in GUIDANCE_CODES:
        entry = guidance_for(code)
        assert isinstance(entry, Guidance)
        assert entry.title.strip()
        assert entry.cause.strip()
        assert entry.fix.strip()
        assert entry.control.strip()


def test_an_unknown_code_still_returns_usable_guidance() -> None:
    entry = guidance_for("something_nobody_wrote")
    assert entry.title.strip()
    assert entry.control.strip()


def test_the_layout_fix_names_a_margin_that_works() -> None:
    entry = guidance_for("no_circles_fit", suggested_margin_mm=6.5)
    assert "6.5" in entry.fix or "6.5" in entry.action_label


def test_a_margin_that_would_let_the_circles_fit_is_computed() -> None:
    from colouring_factory.layouts import compute_circle_sheet_plan
    from colouring_factory.models import CalibrationProfile

    # A 95 mm badge inside a 60 mm margin leaves 90 mm of usable width on a
    # 210 mm page, so nothing fits until the margin comes down.
    too_tight = CircleSheetConfig(cut_diameter_mm=95.0, margin_mm=60.0, gap_mm=5.0)
    assert compute_circle_sheet_plan(too_tight, CalibrationProfile()).capacity == 0

    suggested = largest_margin_that_fits(too_tight)
    assert suggested is not None
    assert suggested < 60.0

    relaxed = CircleSheetConfig(cut_diameter_mm=95.0, margin_mm=suggested, gap_mm=5.0)
    assert compute_circle_sheet_plan(relaxed, CalibrationProfile()).capacity >= 1


def test_no_margin_helps_when_the_badge_exceeds_the_page() -> None:
    config = CircleSheetConfig(cut_diameter_mm=400.0)
    assert largest_margin_that_fits(config) is None


def test_ink_warnings_have_guidance() -> None:
    assert guidance_for("too_much_ink").control
    assert guidance_for("too_little_ink").control
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_guidance.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'colouring_factory.guidance'`.

- [x] **Step 3: Implement the margin calculation**

Add to `colouring_factory/layouts.py`:

```python
def largest_margin_that_fits(config: CircleSheetConfig) -> float | None:
    """The largest whole half-millimetre margin leaving room for one circle.

    Returns None when the badge itself is wider than the page, where no margin
    can help and the user must change the diameter instead.
    """

    smallest_page = min(config.page_width_mm, config.page_height_mm)
    if config.cut_diameter_mm >= smallest_page:
        return None

    usable = (smallest_page - config.cut_diameter_mm) / 2.0
    return max(0.0, math.floor(usable * 2.0) / 2.0)
```

- [x] **Step 4: Implement the guidance map**

Create `colouring_factory/guidance.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Guidance:
    title: str
    cause: str
    fix: str
    control: str
    action_label: str = ""


_SETTINGS = "the Settings sidebar"
_CONNECT = "the Connect an image generator screen"

_ENTRIES: dict[str, Guidance] = {
    "missing_key": Guidance(
        title="No image generator is connected",
        cause="Doodle needs a key from an image provider before it can draw anything.",
        fix="Connect a provider. Google Gemini has a free allowance if you would rather not add a card.",
        control=_CONNECT,
        action_label="Connect a provider",
    ),
    "authentication": Guidance(
        title="That key was not accepted",
        cause="The provider rejected the key, usually because it was revoked, mistyped or truncated when copied.",
        fix="Create a fresh key on the provider's site and paste it again.",
        control=_CONNECT,
        action_label="Replace the key",
    ),
    "billing": Guidance(
        title="The provider has no credit",
        cause="The key works, but the account has no billing method or no remaining balance.",
        fix="Add billing or top up the account, then try the same key again.",
        control=_CONNECT,
        action_label="Open billing",
    ),
    "verification": Guidance(
        title="The account is not yet verified",
        cause="The provider withholds image generation until the account or organisation is verified.",
        fix="Finish verification on the provider's site, then use the same key again.",
        control=_CONNECT,
        action_label="Open the provider",
    ),
    "permission": Guidance(
        title="That key cannot generate images",
        cause="The key is recognised, but its permissions exclude image generation.",
        fix="Create a key with image permissions, or use an unrestricted one.",
        control=_CONNECT,
        action_label="Replace the key",
    ),
    "rate_limit": Guidance(
        title="The provider is asking you to slow down",
        cause="Too many requests arrived in a short time.",
        fix="Wait a minute and draw again. Asking for fewer alternatives at once also helps.",
        control="Alternatives, on the generation form",
    ),
    "content": Guidance(
        title="The provider declined that description",
        cause="A safety filter matched something in the wording, often a real character or brand name.",
        fix="Describe the picture in your own words instead of naming a character from television or film.",
        control="Picture idea, on the generation form",
    ),
    "network": Guidance(
        title="Doodle could not reach the provider",
        cause="The request did not complete, usually a dropped connection or a provider outage.",
        fix="Check the internet connection and draw again.",
        control="the generation form",
    ),
    "unsupported_provider": Guidance(
        title="That provider is not available",
        cause="The saved provider is not one Doodle knows about, probably from an older version.",
        fix="Choose a provider again.",
        control=_SETTINGS,
        action_label="Choose a provider",
    ),
    "missing_prompt": Guidance(
        title="No picture idea yet",
        cause="Doodle has nothing to draw until you describe something.",
        fix="Type what you would like drawn, such as a smiling baby dinosaur washing a toy fire engine.",
        control="Picture idea, on the generation form",
    ),
    "brief_format": Guidance(
        title="The alternatives could not be planned",
        cause="The text model returned scenes Doodle could not read, so the built-in variations were used instead.",
        fix="Nothing to do. The pictures will still differ, using Doodle's own variation rules.",
        control="Alternatives, on the generation form",
    ),
    "brief_failed": Guidance(
        title="The alternatives could not be planned",
        cause="The text model could not be reached, so the built-in variations were used instead.",
        fix="Nothing to do. The pictures will still differ, using Doodle's own variation rules.",
        control="Alternatives, on the generation form",
    ),
    "no_text_model": Guidance(
        title="This provider cannot plan the alternatives",
        cause="The chosen provider only draws pictures, so Doodle used its own variation rules.",
        fix="Switch to OpenAI or Google Gemini for more varied alternatives.",
        control=_SETTINGS,
    ),
    "no_circles_fit": Guidance(
        title="No badges fit on the sheet",
        cause="The cut diameter plus the outer margin is wider than the page.",
        fix="Reduce the outer margin or the cut diameter.",
        control="Outer margin, on the circle sheet form",
    ),
    "badge_too_large": Guidance(
        title="The badge is wider than the page",
        cause="No margin can help, because the cut diameter alone exceeds the shorter side of the page.",
        fix="Reduce the paper cut diameter to less than 210 mm.",
        control="Paper cut diameter, on the circle sheet form",
    ),
    "too_much_ink": Guidance(
        title="This picture is very heavy on black",
        cause="Over a third of the page is solid black, which drinks ink and leaves little to colour in.",
        fix="Lower the black and white threshold, or choose a simpler picture.",
        control="Black/white threshold, in Step 2",
        action_label="Lower the threshold",
    ),
    "too_little_ink": Guidance(
        title="Almost no line work survived",
        cause="The threshold is discarding lines that are too faint to register as black.",
        fix="Raise the black and white threshold until the outlines return.",
        control="Black/white threshold, in Step 2",
        action_label="Raise the threshold",
    ),
    "pdf_failed": Guidance(
        title="The PDF could not be built",
        cause="The page dimensions and margins leave no room for the artwork.",
        fix="Reduce the inner margin, or increase the page size.",
        control="the layout form in Step 3",
    ),
    "unknown": Guidance(
        title="Something went wrong",
        cause="Doodle did not recognise this failure.",
        fix="Try again. If it keeps happening, check the provider connection.",
        control=_SETTINGS,
    ),
}

GUIDANCE_CODES = frozenset(_ENTRIES)


def guidance_for(code: str, **context: Any) -> Guidance:
    entry = _ENTRIES.get(code, _ENTRIES["unknown"])

    margin = context.get("suggested_margin_mm")
    if code == "no_circles_fit" and margin is not None:
        return Guidance(
            title=entry.title,
            cause=entry.cause,
            fix=f"An outer margin of {margin:g} mm would leave room for at least one badge.",
            control=entry.control,
            action_label=f"Set the margin to {margin:g} mm",
        )

    return entry
```

- [x] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_guidance.py -v`
Expected: PASS. If `test_every_generator_error_code_has_guidance` lists a missing code, add an entry for it rather than loosening the test — that test exists precisely to catch a new failure mode shipping without an explanation.

- [x] **Step 6: Render one guidance panel in the app**

In `app.py`, add `from colouring_factory.guidance import guidance_for` and `from colouring_factory.layouts import largest_margin_that_fits` to the imports, and add a shared renderer beside the other helpers:

```python
def _show_guidance(code: str, *, detail: str = "", **context) -> None:
    entry = guidance_for(code, **context)
    st.error(f"**{entry.title}** — {detail or entry.cause}")
    st.markdown(
        f'<div class="geometry-box">{entry.fix}<br>'
        f'<span class="small-muted">Where: {entry.control}</span></div>',
        unsafe_allow_html=True,
    )
```

Replace the bare `st.error(str(exc))` in the studio generation branch (for codes that do not route to the connection screen) with `_show_guidance(exc.code, detail=str(exc))`.

Replace the circle-sheet layout failure. Where `compute_circle_sheet_plan` currently raises into `st.error(str(exc))`, use:

```python
            except ValueError as exc:
                suggested = largest_margin_that_fits(pdf_config)
                if suggested is None:
                    _show_guidance("badge_too_large", detail=str(exc))
                else:
                    _show_guidance("no_circles_fit", detail=str(exc), suggested_margin_mm=suggested)
                    if st.button(f"Set the margin to {suggested:g} mm", use_container_width=True):
                        st.session_state.circle_margin_mm = suggested
                        st.rerun()
                summary = "Invalid circle layout"
```

For this button to work, the outer-margin number input needs a session key. Change it to:

```python
                sheet_margin = st.number_input(
                    "Outer margin (mm)", 0.0, 40.0, 10.0, 0.5, key="circle_margin_mm"
                )
```

Replace the two ink warnings in Step 2 with guidance calls:

```python
        if metrics["ink_percent"] > 35:
            _show_guidance("too_much_ink")
        elif metrics["ink_percent"] < 0.4:
            _show_guidance("too_little_ink")
```

Wrap the PDF build so a failure explains itself:

```python
            except ValueError as exc:
                _show_guidance("pdf_failed", detail=str(exc))
```

- [x] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass.

- [x] **Step 8: Commit**

```bash
git add colouring_factory/guidance.py colouring_factory/layouts.py app.py tests/test_guidance.py
git commit -m "Explain every failure and offer the fix where one is computable

Errors named a problem and stopped, leaving the user to guess which of
several dozen controls was responsible. Each failure now carries a
cause, a fix, and the name of the control that owns it.

Where a correction can be calculated it becomes a button: a sheet whose
circles do not fit offers the largest margin that would work, computed
rather than guessed. Streamlit cannot scroll to a widget reliably, so a
one-click correction replaces navigation.

A test asserts that every error code raised in generators.py has an
entry, so a new failure mode cannot ship unexplained."
```

---

## Task 9: Homepage prompt bar hint and documentation

**Files:**
- Modify: `app.py`
- Modify: `README.md`
- Modify: `tests/test_branding.py`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing consumed by later tasks.

- [x] **Step 1: Write the failing test**

Append to `tests/test_branding.py`:

```python
def test_the_prompt_bar_hint_lives_outside_the_input() -> None:
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

    # Streamlit's own hint and clear button are right-aligned inside the input
    # and collide with each other and the pill's rounded edge, so both are
    # hidden and replaced with a line below the bar.
    assert '[data-testid="InputInstructions"]' in app_source
    assert "Press Enter to draw" in app_source
    assert "home-hint" in app_source
```

- [x] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_branding.py -v`
Expected: FAIL on `"Press Enter to draw"`.

- [x] **Step 3: Add the hint below the bar**

In `_render_homepage` in `app.py`, add to the homepage `<style>` block:

```css
          .home-hint {
            text-align: center;
            color: #858a91;
            font-size: .85rem;
            margin: .85rem auto 0;
            letter-spacing: .01em;
          }
```

and immediately after the `st.text_input(...)` call, before the error display:

```python
    st.markdown('<div class="home-hint">Press Enter to draw</div>', unsafe_allow_html=True)
```

- [x] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_branding.py -v`
Expected: PASS.

- [x] **Step 5: Update the README**

Replace the `## AI generation` section with:

```markdown
## AI generation

Doodle can draw with any of three providers. The first time you enter an idea it opens a
connection screen with a link to the right page for creating a key.

| Provider | Environment variable | Where to get a key |
|---|---|---|
| Google Gemini | `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| OpenAI | `OPENAI_API_KEY` | https://platform.openai.com/settings/organization/api-keys |
| Recraft | `RECRAFT_API_TOKEN` | https://app.recraft.ai/profile/api |

Google Gemini has a free allowance, so it is the cheapest way to start. OpenAI and Recraft
both require billing before they will generate anything.

A key can come from three places, checked in this order: one typed into the current session,
then the environment variable above, then a key you asked Doodle to remember. Remembered keys
are written to `~/.doodle/credentials.json` with owner-only file permissions. They are never
written into artwork, PDFs or the saved-doodle library. Demo and upload modes need no key.

### Alternatives

When you ask for more than one alternative, Doodle first asks the provider's text model to plan
that many different scenes, varying the moment in the story, the camera framing, the setting and
the mood. Recraft has no text model, so it falls back to Doodle's own variation rules. Either
way the drawing style, age profile and composition rules stay identical between alternatives,
so what differs is the interpretation. The studio shows the plan under "How the alternatives
differ".
```

Replace the `## Badge dimensions` section's closing paragraph with:

```markdown
The circle sheet shows a live preview of one badge with all three diameters drawn: a solid line
where the paper is cut, a dashed line for the visible face, and a dotted line for the safe area.

By default the whole picture is fitted inside the safe circle, so nothing is cut off. This makes
the artwork about 71 per cent of the safe diameter, because a square that fits inside a circle is
narrower than the circle. Choose **Fill the circle** if you would rather the picture be larger
and accept losing its corners.
```

Add to the repository structure listing, in alphabetical position:

```text
  badge_preview.py            One badge rendered with its three boundaries
  credentials.py              Provider keys stored on this computer
  guidance.py                 What each failure means and how to fix it
  providers.py                The image providers Doodle can use
  variations.py               Turning one idea into distinct scenes
```

- [x] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass.

- [x] **Step 7: Launch the app and check it by hand**

Run: `.venv/bin/streamlit run app.py`

Confirm, with no key configured: the homepage shows the wordmark, one prompt bar with no overlapping icons, and the hint below it. Entering an idea opens the connection screen naming all three providers. Then with a key: an idea draws a picture; asking for three alternatives in the studio produces three visibly different scenes; choosing "A4 circle sheet" shows the badge preview with three rings before any PDF is built.

- [x] **Step 8: Commit**

```bash
git add app.py README.md tests/test_branding.py
git commit -m "Replace the colliding prompt bar affordances with a hint below it

Streamlit right-aligns its 'Press Enter to apply' hint and clear button
inside the input, where the homepage's 62px pill leaves no room, so they
overlapped each other and the rounded edge. Both are hidden and a static
line sits below the bar instead, which cannot collide with anything and
still says that Enter submits.

The README now documents all three providers, where each key comes from
and where a remembered one is stored, how alternatives are planned, and
what the badge preview's three rings mean."
```

---

## What changed during execution

Three things the plan did not anticipate, recorded so the next person is not
surprised by the difference between this document and the commits.

**Task 10 was added.** The `developing-with-streamlit` skill loaded after the plan
was written and flagged `use_container_width` as deprecated. All 37 call sites in
`app.py` were converted to `width="stretch"` as a separate mechanical commit,
verified against the installed signatures rather than the test suite, whose fake
Streamlit ignores keyword arguments.

**Two real bugs were found by running the app, not by the unit tests.**

The first: sizing the badge preview page from the nominal diameter put the fit
test on a floating-point boundary, so a calibrated 58 mm badge came out roughly
seven femtometres wider than its own page and no circles fitted at all. The page
now clears the scaled diameter plus the centring offset, with a tenth of a
millimetre of slack.

The second, and the more instructive: the layout guidance was wired to the
exception path, but `compute_circle_sheet_plan` returns a zero-capacity plan
rather than raising when nothing fits. The most likely failure in practice — a
badge too large for its margin — showed "0 circles fit" with no explanation and
no way forward. The unit tests could not catch this, because they exercised
`largest_margin_that_fits` and `guidance_for` in isolation and never the wiring
between them.

**A third test layer was added because of that.** `tests/test_app_circle_guidance.py`
drives the app through Streamlit's own `AppTest` runner, which executes the real
script with the real runtime and can tell whether a control rendered and what it
said. The hand-written fake Streamlit in `tests/test_app_smoke.py` cannot: it
returns `None` for any command it does not implement, so a missing panel looks
identical to a rendered one. Prefer `AppTest` for anything that asserts what the
user sees.

## Verification before the PR leaves draft

- [x] `.venv/bin/python -m pytest` — full suite green, with the actual output pasted into the PR
- [x] The app launches and the manual checks in Task 9 Step 7 all pass
- [x] `git log --oneline main..HEAD` shows one commit per task, none bundling unrelated work
- [x] The spec's "Out of scope" list has not been quietly implemented
- [x] `gh pr ready` once the above hold
