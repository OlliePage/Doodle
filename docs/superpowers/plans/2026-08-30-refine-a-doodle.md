# Refining a Doodle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change a generated colouring page with a written instruction instead of regenerating it from the original idea, keeping every version in a chain you can step back through.

**Architecture:** The provider registry, credential storage and error guidance already exist from #4 and #8. This adds an editing call beside the existing generation call in `generators.py`, a pure version-chain module with no Streamlit import, a refinement prompt builder, and the interface to drive them. The split between the Streamlit file and the pure package is preserved throughout.

**Tech Stack:** Python 3.11+, Streamlit 1.62, `openai` package for OpenAI, `urllib.request` from the standard library for Gemini and Recraft. Pytest 9 with Streamlit's `AppTest`.

**Spec:** `docs/superpowers/specs/2026-08-30-refine-a-doodle-design.md`

## Global Constraints

- `from __future__ import annotations` at the top of every module, matching the package.
- **No new runtime dependencies.** Recraft needs a multipart body; build it with the standard library, not `requests`.
- **No test may make a real network call or spend money.** Stub `urlopen` and the OpenAI client as the existing tests do.
- British English in user-facing copy. Sentence casing for labels. Material Symbols icons (`icon=":material/name:"`), never emoji.
- `width="stretch"`, never the deprecated `use_container_width`.
- Prefer native Streamlit elements over injected HTML; `st.container(border=True)` for grouping.
- **Every new button is clicked in a test, never merely asserted to exist.** A recovery button shipped broken past that omission in #8.
- Add an import and its first use in the same edit; a formatter hook strips imports that are momentarily unused.
- No `Co-Authored-By` trailer, no generated-with footer. Commit as the local git identity.
- Run `.venv/bin/python -m pytest` from the repository root. Green before every commit. Baseline is **151 passing**.
- Verified provider facts, read from live documentation on 2026-08-30:
  - OpenAI: `client.images.edit(model=..., image=..., prompt=..., size=..., input_fidelity=...)`; `input_fidelity` **higher means closer** to the original.
  - Gemini: `POST https://generativelanguage.googleapis.com/v1beta/interactions`, header `x-goog-api-key`, `input` is `[{"type": "text", "text": ...}, {"type": "image", "mime_type": "image/png", "data": "<base64>"}]`. Same models as generation. No closeness control.
  - Recraft: `POST https://external.api.recraft.ai/v1/images/imageToImage`, multipart, required fields `image`, `prompt`, `strength`. **`strength` is difference, so lower means closer**: 0 is "almost identical", 1 is "minimal similarity".

---

## File Structure

**Created:**

| File | Responsibility |
|---|---|
| `colouring_factory/history.py` | The version chain: starting one, appending, and finding an entry's ancestry. Pure data, no Streamlit, no I/O. |
| `tests/test_history.py` | Chain behaviour. |
| `tests/test_refine.py` | Each provider's edit request shape and failure handling. |
| `tests/test_app_refine.py` | The refine control driven on the real Streamlit runtime. |

**Modified:**

| File | Change |
|---|---|
| `colouring_factory/providers.py` | `supports_edit` and `edit_closeness` on every spec. |
| `colouring_factory/generators.py` | `refine_with_provider` and the three adapters; a multipart helper. |
| `colouring_factory/prompts.py` | `build_refinement_prompt`. |
| `colouring_factory/guidance.py` | Entries for `edit_unsupported` and `edit_failed`. |
| `app.py` | Refine box and version strip on the result screen and in the studio. |
| `README.md` | A section on refining. |

---

## Task 1: Declare the editing capability

**Files:**
- Modify: `colouring_factory/providers.py`
- Modify: `tests/test_providers.py`

**Interfaces:**
- Produces: `ProviderSpec.supports_edit: bool`, `ProviderSpec.edit_closeness: float`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_providers.py`:

```python
def test_every_provider_declares_whether_it_can_edit() -> None:
    for provider_id, spec in PROVIDERS.items():
        assert isinstance(spec.supports_edit, bool)
        assert 0.0 <= spec.edit_closeness <= 1.0, provider_id


def test_all_three_providers_can_edit_today() -> None:
    assert {p for p, s in PROVIDERS.items() if s.supports_edit} == {
        "openai",
        "google",
        "recraft",
    }


def test_closeness_is_stored_on_one_scale_where_high_means_close() -> None:
    # OpenAI's input_fidelity and Recraft's strength run in opposite directions.
    # Storing raw vendor values would let 0.9 be copied between them and mean
    # the opposite. This field always means "stay close"; adapters translate.
    for spec in PROVIDERS.values():
        if spec.supports_edit:
            assert spec.edit_closeness >= 0.5, (
                f"{spec.id} would drift; refinement should stay close by default"
            )
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: FAIL with `AttributeError: 'ProviderSpec' object has no attribute 'supports_edit'`.

- [ ] **Step 3: Add the fields**

In `colouring_factory/providers.py`, after `billing_button_label`:

```python
    supports_edit: bool = False
    # One scale, 1.0 meaning "stay as close to the original as possible".
    # OpenAI's input_fidelity runs the same way and Recraft's strength runs
    # backwards, so each adapter translates rather than storing raw values.
    edit_closeness: float = 0.85
```

Then set `supports_edit=True` on all three entries. Leave `edit_closeness` at its default on each.

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add colouring_factory/providers.py tests/test_providers.py
git commit -m "Declare which providers can edit an existing picture

All three can today, but the capability is declared per provider so a
future one that cannot needs no if-else on its name in the interface.

Closeness is stored on a single scale where 1.0 means stay as close to
the original as possible. OpenAI measures fidelity and Recraft measures
difference, so the raw values run in opposite directions; storing them
unconverted would let 0.9 be copied between providers and mean the
opposite of what was intended."
```

---

## Task 2: Refine with each provider

**Files:**
- Modify: `colouring_factory/generators.py`
- Create: `tests/test_refine.py`

**Interfaces:**
- Consumes: `GeneratorError`, `_normalise_error`, `_read_image_payload`, `_google_image_block`, `GOOGLE_ENDPOINT` from the existing module.
- Produces:
  - `generators.RECRAFT_EDIT_ENDPOINT`
  - `generators.refine_with_openai(*, api_key, image_bytes, prompt, model, size, quality="medium", closeness=0.85, mask_bytes=None) -> GeneratedArtwork`
  - `generators.refine_with_google(*, api_key, image_bytes, prompt, model, size) -> GeneratedArtwork`
  - `generators.refine_with_recraft(*, api_key, image_bytes, prompt, model, closeness=0.85, random_seed=None) -> GeneratedArtwork`
  - `generators.refine_with_provider(*, provider_id, api_key, image_bytes, prompt, model, size, quality="medium", mask_bytes=None, random_seed=None) -> GeneratedArtwork`
  - `generators._multipart_body(fields, files) -> tuple[bytes, str]` returning the body and its content type

- [ ] **Step 1: Write the failing test**

Create `tests/test_refine.py`:

```python
import base64
import json
import sys
import types
from io import BytesIO

import pytest

from colouring_factory import generators
from colouring_factory.generators import (
    GeneratorError,
    refine_with_google,
    refine_with_provider,
    refine_with_recraft,
)

PIXEL = base64.b64encode(b"fake-png-bytes").decode("ascii")
ORIGINAL = b"\x89PNG\r\n\x1a\noriginal-image-bytes"


class _FakeResponse(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()
        return False


def _google_image_reply() -> _FakeResponse:
    payload = {
        "steps": [
            {"type": "model_output", "content": [{"type": "image", "data": PIXEL}]}
        ]
    }
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


def _recraft_reply() -> _FakeResponse:
    return _FakeResponse(json.dumps({"data": [{"b64_json": PIXEL}]}).encode("utf-8"))


def test_google_sends_the_instruction_and_the_image_together(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = dict(request.headers)
        return _google_image_reply()

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    art = refine_with_google(
        api_key="AIza-test",
        image_bytes=ORIGINAL,
        prompt="give the bear a hat",
        model="gemini-3.1-flash-image",
        size="3:4",
    )

    blocks = captured["body"]["input"]
    assert blocks[0] == {"type": "text", "text": "give the bear a hat"}
    assert blocks[1]["type"] == "image"
    assert blocks[1]["mime_type"] == "image/png"
    assert base64.b64decode(blocks[1]["data"]) == ORIGINAL
    assert captured["headers"]["X-goog-api-key"] == "AIza-test"
    assert art.image_bytes == b"fake-png-bytes"
    assert art.metadata["instruction"] == "give the bear a hat"


def test_recraft_sends_multipart_with_a_low_strength(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["type"] = request.headers.get("Content-type", "")
        captured["raw"] = request.data
        return _recraft_reply()

    monkeypatch.setattr(generators, "urlopen", fake_urlopen)

    refine_with_recraft(
        api_key="token",
        image_bytes=ORIGINAL,
        prompt="give the bear a hat",
        model="recraftv4_1",
        closeness=0.85,
    )

    assert captured["url"] == generators.RECRAFT_EDIT_ENDPOINT
    assert captured["type"].startswith("multipart/form-data; boundary=")
    assert ORIGINAL in captured["raw"]
    assert b'name="prompt"' in captured["raw"]

    # strength is difference, so closeness 0.85 must send roughly 0.15, not 0.85.
    body = captured["raw"].decode("latin-1")
    strength = body.split('name="strength"')[1].split("\r\n\r\n")[1].split("\r\n")[0]
    assert float(strength) == pytest.approx(0.15, abs=0.01)


def test_openai_asks_to_stay_faithful_to_the_original(monkeypatch) -> None:
    calls = []

    class _Images:
        def edit(self, **kwargs):
            calls.append(kwargs)
            item = types.SimpleNamespace(b64_json=PIXEL, url=None, revised_prompt=None)
            return types.SimpleNamespace(data=[item])

    class _Client:
        def __init__(self, **kwargs):
            self.images = _Images()

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = _Client
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    generators.refine_with_openai(
        api_key="sk-test",
        image_bytes=ORIGINAL,
        prompt="give the bear a hat",
        model="gpt-image-2",
        size="1024x1536",
        closeness=0.85,
    )

    # input_fidelity runs the same way as closeness, so it passes straight through.
    assert calls[0]["input_fidelity"] == pytest.approx(0.85)
    assert calls[0]["prompt"] == "give the bear a hat"


def test_a_missing_key_is_refused_before_any_request() -> None:
    for provider in ("openai", "google", "recraft"):
        with pytest.raises(GeneratorError) as caught:
            refine_with_provider(
                provider_id=provider,
                api_key="   ",
                image_bytes=ORIGINAL,
                prompt="x",
                model="m",
                size="3:4",
            )
        assert caught.value.code == "missing_key"


def test_a_provider_that_cannot_edit_says_so() -> None:
    with pytest.raises(GeneratorError) as caught:
        refine_with_provider(
            provider_id="nonsense",
            api_key="k",
            image_bytes=ORIGINAL,
            prompt="x",
            model="m",
            size="3:4",
        )
    assert caught.value.code in {"unsupported_provider", "edit_unsupported"}


def test_an_empty_reply_is_explained(monkeypatch) -> None:
    empty = _FakeResponse(json.dumps({"steps": []}).encode("utf-8"))
    monkeypatch.setattr(generators, "urlopen", lambda request, timeout=None: empty)

    with pytest.raises(GeneratorError) as caught:
        refine_with_google(
            api_key="AIza-test",
            image_bytes=ORIGINAL,
            prompt="x",
            model="gemini-3.1-flash-image",
            size="3:4",
        )
    assert caught.value.code in {"content", "edit_failed"}


def test_an_empty_instruction_is_refused() -> None:
    with pytest.raises(ValueError):
        refine_with_provider(
            provider_id="google",
            api_key="k",
            image_bytes=ORIGINAL,
            prompt="   ",
            model="m",
            size="3:4",
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_refine.py -v`
Expected: FAIL with `ImportError: cannot import name 'refine_with_google'`.

- [ ] **Step 3: Add the multipart helper**

Recraft needs a multipart body and no dependency may be added, so build one. Add to `colouring_factory/generators.py`:

```python
RECRAFT_EDIT_ENDPOINT = "https://external.api.recraft.ai/v1/images/imageToImage"


def _multipart_body(
    fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]
) -> tuple[bytes, str]:
    """Encode a multipart/form-data body without adding a dependency."""

    boundary = f"----doodle{uuid.uuid4().hex}"
    parts: list[bytes] = []

    for name, value in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(f"{value}\r\n".encode())

    for name, (filename, payload, content_type) in files.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
        parts.append(payload)
        parts.append(b"\r\n")

    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"
```

Add `import uuid` beside the other imports, in the same edit.

- [ ] **Step 4: Add the three adapters and the dispatcher**

Add to `colouring_factory/generators.py`:

```python
def _check_instruction(prompt: str) -> str:
    instruction = prompt.strip()
    if not instruction:
        raise ValueError("Describe the change you would like.")
    return instruction


def refine_with_openai(
    *,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str = "gpt-image-2",
    size: str = "1024x1536",
    quality: str = "medium",
    closeness: float = 0.85,
    mask_bytes: bytes | None = None,
) -> GeneratedArtwork:
    instruction = _check_instruction(prompt)
    if not api_key.strip():
        raise GeneratorError(
            "Connect OpenAI with an API key before changing artwork.",
            provider="OpenAI",
            code="missing_key",
        )

    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover - incomplete installation only.
        raise GeneratorError(
            "The OpenAI Python package is not installed. Run pip install -r requirements.txt.",
            provider="OpenAI",
            code="edit_failed",
        ) from exc

    request_kwargs: dict[str, Any] = {
        "model": model,
        "image": ("doodle.png", BytesIO(image_bytes), "image/png"),
        "prompt": instruction,
        "size": size,
        # Runs the same way as closeness: higher stays nearer the original.
        "input_fidelity": closeness,
    }
    if mask_bytes:
        request_kwargs["mask"] = ("mask.png", BytesIO(mask_bytes), "image/png")

    try:
        client = OpenAI(api_key=api_key.strip(), timeout=240.0, max_retries=2)
        result = client.images.edit(**request_kwargs)
        if not result.data:
            raise GeneratorError(
                "OpenAI returned no changed image.", provider="OpenAI", code="edit_failed"
            )
        payload = _read_image_payload(result.data[0])
    except GeneratorError:
        raise
    except Exception as exc:
        raise _normalise_error("OpenAI", exc) from exc

    return GeneratedArtwork(
        image_bytes=payload,
        prompt=instruction,
        provider="OpenAI",
        model=model,
        metadata={"instruction": instruction, "size": size, "quality": quality},
    )


def refine_with_google(
    *,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str = "gemini-3.1-flash-image",
    size: str = "3:4",
) -> GeneratedArtwork:
    instruction = _check_instruction(prompt)
    if not api_key.strip():
        raise GeneratorError(
            "Connect Google Gemini with an API key before changing artwork.",
            provider="Google Gemini",
            code="missing_key",
        )

    body = {
        "model": model,
        "input": [
            {"type": "text", "text": instruction},
            {
                "type": "image",
                "mime_type": "image/png",
                "data": base64.b64encode(image_bytes).decode("ascii"),
            },
        ],
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
        raise _normalise_error(
            "Google Gemini", exc, status_code=exc.code, details=detail
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _normalise_error("Google Gemini", exc) from exc

    encoded = _google_image_block(payload)
    if not encoded:
        raise GeneratorError(
            "Google Gemini returned no changed image. It may have declined the instruction.",
            provider="Google Gemini",
            code="content",
        )

    return GeneratedArtwork(
        image_bytes=_read_image_payload({"b64_json": encoded}),
        prompt=instruction,
        provider="Google Gemini",
        model=model,
        metadata={"instruction": instruction, "size": size},
    )


def refine_with_recraft(
    *,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str = "recraftv4_1",
    closeness: float = 0.85,
    random_seed: int | None = None,
) -> GeneratedArtwork:
    instruction = _check_instruction(prompt)
    if not api_key.strip():
        raise GeneratorError(
            "Connect Recraft with an API token before changing artwork.",
            provider="Recraft",
            code="missing_key",
        )

    # Recraft's strength is the difference from the original, the inverse of
    # closeness: its documentation calls 0 "almost identical".
    strength = round(max(0.0, min(1.0, 1.0 - closeness)), 3)
    fields = {
        "prompt": instruction,
        "strength": str(strength),
        "model": model,
        "n": "1",
        "response_format": "b64_json",
    }
    if random_seed is not None:
        fields["random_seed"] = str(int(random_seed))

    payload_bytes, content_type = _multipart_body(
        fields, {"image": ("doodle.png", image_bytes, "image/png")}
    )
    request = Request(
        RECRAFT_EDIT_ENDPOINT,
        data=payload_bytes,
        headers={
            "Authorization": f"Bearer {api_key.strip()}",
            "Content-Type": content_type,
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
        raise _normalise_error(
            "Recraft", exc, status_code=exc.code, details=detail
        ) from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise _normalise_error("Recraft", exc) from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        raise GeneratorError(
            "Recraft returned no changed image.", provider="Recraft", code="edit_failed"
        )

    return GeneratedArtwork(
        image_bytes=_read_image_payload(data[0]),
        prompt=instruction,
        provider="Recraft",
        model=model,
        metadata={"instruction": instruction, "strength": strength},
    )


def refine_with_provider(
    *,
    provider_id: str,
    api_key: str,
    image_bytes: bytes,
    prompt: str,
    model: str,
    size: str,
    quality: str = "medium",
    mask_bytes: bytes | None = None,
    random_seed: int | None = None,
) -> GeneratedArtwork:
    from .providers import PROVIDERS, get_provider

    provider = provider_id.strip().lower()
    if provider not in PROVIDERS:
        raise GeneratorError(
            f"Unsupported image provider: {provider_id}", code="unsupported_provider"
        )

    spec = get_provider(provider)
    if not spec.supports_edit:
        raise GeneratorError(
            f"{spec.label} cannot change an existing picture.",
            provider=spec.label,
            code="edit_unsupported",
        )

    if provider == "openai":
        return refine_with_openai(
            api_key=api_key,
            image_bytes=image_bytes,
            prompt=prompt,
            model=model,
            size=size,
            quality=quality,
            closeness=spec.edit_closeness,
            mask_bytes=mask_bytes,
        )
    if provider == "google":
        return refine_with_google(
            api_key=api_key,
            image_bytes=image_bytes,
            prompt=prompt,
            model=model,
            size=size,
        )
    return refine_with_recraft(
        api_key=api_key,
        image_bytes=image_bytes,
        prompt=prompt,
        model=model,
        closeness=spec.edit_closeness,
        random_seed=random_seed,
    )
```

The `providers` import is local to the function so `providers.py` can keep importing nothing from `generators.py` and the dependency stays one-way.

- [ ] **Step 5: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_refine.py -v`
Expected: PASS. If `test_a_missing_key_is_refused_before_any_request` fails for one provider, the instruction check runs before the key check in that adapter; both orders are defensible, so align the test with the code rather than the reverse.

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass, 151 plus the new ones.

- [ ] **Step 7: Commit**

```bash
git add colouring_factory/generators.py tests/test_refine.py
git commit -m "Change an existing picture with a written instruction

Adds an editing call beside the generation one for all three providers.
Gemini reuses its generation endpoint with the picture as a second input
block; OpenAI has a dedicated edit call; Recraft needs multipart, which
is built with the standard library rather than adding a dependency.

The two closeness controls run in opposite directions. OpenAI's
input_fidelity measures how near the result stays, while Recraft's
strength measures how far it moves, so the adapter inverts it. A test
asserts a closeness of 0.85 reaches Recraft as a strength of 0.15."
```

---

## Task 3: Keep the style contract on a refinement

**Files:**
- Modify: `colouring_factory/prompts.py`
- Modify: `tests/test_prompts.py`

**Interfaces:**
- Produces: `prompts.build_refinement_prompt(instruction, *, style_name="Toddler bold", age_profile="2-3 years", target="A4 page") -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_prompts.py`:

```python
from colouring_factory.prompts import build_refinement_prompt


def test_a_refinement_keeps_the_colouring_book_rules() -> None:
    prompt = build_refinement_prompt("give the bear a party hat")
    assert "give the bear a party hat" in prompt
    assert "Black line work only" in prompt
    assert "Pure white background" in prompt


def test_a_refinement_asks_for_everything_else_to_stay() -> None:
    prompt = build_refinement_prompt("give the bear a party hat").lower()
    assert "unchanged" in prompt or "leave everything else" in prompt


def test_a_refinement_carries_the_style_and_age_profile() -> None:
    toddler = build_refinement_prompt("add a hat", age_profile="2-3 years")
    preschool = build_refinement_prompt("add a hat", age_profile="4-5 years")
    assert toddler != preschool


def test_an_empty_instruction_is_refused() -> None:
    with pytest.raises(ValueError):
        build_refinement_prompt("   ")
```

Add `import pytest` to the top of the file in the same edit if it is not already there.

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_refinement_prompt'`.

- [ ] **Step 3: Implement it**

Add to `colouring_factory/prompts.py`:

```python
def build_refinement_prompt(
    instruction: str,
    *,
    style_name: str = "Toddler bold",
    age_profile: str = "2-3 years",
    target: str = "A4 page",
) -> str:
    """Wrap a change request in the same rules the original drawing obeyed.

    Sent bare, an instruction loses the colouring-book contract and comes back
    shaded or grey, because the model has no reason to know the picture is line
    art meant for crayons.
    """

    instruction = instruction.strip()
    if not instruction:
        raise ValueError("Describe the change you would like.")

    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Toddler bold"])
    age_rule = AGE_RULES.get(age_profile, AGE_RULES["2-3 years"])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    prompt = f"""
    Change this black-and-white colouring-book illustration as described, and
    change nothing else.

    Requested change: {instruction}

    Leave every other part of the scene unchanged: the same characters, poses,
    props, background and composition.

    Visual rules, which the changed picture must still obey:
    - Pure white background.
    - Black line work only: no colour, grey, shading, shadows, gradients, hatching or texture.
    - Smooth rounded outlines, friendly expressions and coherent anatomy.
    - Large, closed areas that are pleasant to colour with crayons.
    - No border, words, letters, numbers, logos, signatures or watermark.
    - Nothing important may be cropped by the image edge.

    Style profile: {style.instruction}
    Child profile: {age_rule}
    Composition profile: {target_rule}
    """

    return dedent(prompt).strip()
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_prompts.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add colouring_factory/prompts.py tests/test_prompts.py
git commit -m "Keep the colouring-book rules on a refinement

An instruction sent bare loses the style contract and comes back shaded,
because nothing tells the model the picture is line art for crayons. The
refinement prompt repeats the same rules the original obeyed and asks
explicitly for everything else in the scene to stay as it is."
```

---

## Task 4: The version chain

**Files:**
- Create: `colouring_factory/history.py`
- Create: `tests/test_history.py`

**Interfaces:**
- Produces:
  - `history.Version` frozen dataclass with `artwork: GeneratedArtwork`, `instruction: str`, `parent: int | None`
  - `history.start(artwork) -> tuple[Version, ...]`
  - `history.append(chain, artwork, instruction, parent) -> tuple[Version, ...]`
  - `history.ancestry(chain, index) -> tuple[int, ...]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_history.py`:

```python
import pytest

from colouring_factory.history import Version, ancestry, append, start
from colouring_factory.models import GeneratedArtwork


def _art(tag: str) -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=tag.encode(), prompt=tag, provider="Test", model="test"
    )


def test_a_chain_starts_with_one_unattributed_version() -> None:
    chain = start(_art("original"))
    assert len(chain) == 1
    assert chain[0].instruction == ""
    assert chain[0].parent is None


def test_appending_records_the_instruction_and_the_parent() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hatted"), "add a hat", parent=0)
    assert len(chain) == 2
    assert chain[1].instruction == "add a hat"
    assert chain[1].parent == 0


def test_the_chain_is_append_only() -> None:
    # Backing out of a direction must never destroy what came after, so a
    # refinement from an earlier version adds rather than truncates.
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    chain = append(chain, _art("scarf"), "add a scarf", parent=1)
    chain = append(chain, _art("boots"), "add boots", parent=0)

    assert len(chain) == 4
    assert [v.parent for v in chain] == [None, 0, 1, 0]
    assert chain[2].instruction == "add a scarf"


def test_versions_are_immutable() -> None:
    chain = start(_art("original"))
    with pytest.raises(Exception):
        chain[0].instruction = "changed"


def test_appending_returns_a_new_chain() -> None:
    first = start(_art("original"))
    second = append(first, _art("hat"), "add a hat", parent=0)
    assert len(first) == 1
    assert first is not second


def test_ancestry_walks_back_to_the_original() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    chain = append(chain, _art("scarf"), "add a scarf", parent=1)
    assert ancestry(chain, 2) == (0, 1, 2)
    assert ancestry(chain, 0) == (0,)


def test_an_unknown_parent_is_refused() -> None:
    chain = start(_art("original"))
    with pytest.raises(ValueError):
        append(chain, _art("hat"), "add a hat", parent=7)


def test_an_empty_instruction_is_refused() -> None:
    chain = start(_art("original"))
    with pytest.raises(ValueError):
        append(chain, _art("hat"), "   ", parent=0)


def test_starting_again_abandons_the_previous_chain() -> None:
    chain = start(_art("original"))
    chain = append(chain, _art("hat"), "add a hat", parent=0)
    fresh = start(_art("different"))
    assert len(fresh) == 1
    assert fresh[0].artwork.prompt == "different"
```

- [ ] **Step 2: Run to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_history.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'colouring_factory.history'`.

- [ ] **Step 3: Implement it**

Create `colouring_factory/history.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from .models import GeneratedArtwork


@dataclass(frozen=True)
class Version:
    artwork: GeneratedArtwork
    instruction: str
    parent: int | None


def start(artwork: GeneratedArtwork) -> tuple[Version, ...]:
    """Begin a fresh chain. Any previous chain is abandoned, not merged."""

    return (Version(artwork=artwork, instruction="", parent=None),)


def append(
    chain: tuple[Version, ...],
    artwork: GeneratedArtwork,
    instruction: str,
    parent: int,
) -> tuple[Version, ...]:
    """Add a version derived from `parent`, without disturbing what came after.

    Append-only by design: refining from an earlier version after exploring a
    direction must not delete the direction that was explored.
    """

    instruction = instruction.strip()
    if not instruction:
        raise ValueError("A refinement needs an instruction.")
    if not 0 <= parent < len(chain):
        raise ValueError(f"No version {parent} to refine from.")

    return chain + (Version(artwork=artwork, instruction=instruction, parent=parent),)


def ancestry(chain: tuple[Version, ...], index: int) -> tuple[int, ...]:
    """Indices from the original down to `index`, in order."""

    if not 0 <= index < len(chain):
        raise ValueError(f"No version {index}.")

    line: list[int] = []
    cursor: int | None = index
    while cursor is not None:
        line.append(cursor)
        cursor = chain[cursor].parent
    return tuple(reversed(line))
```

- [ ] **Step 4: Run to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_history.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add colouring_factory/history.py tests/test_history.py
git commit -m "Add an append-only version chain for refinements

Each entry records the artwork, the instruction that produced it and the
version it came from. Refining from an earlier version adds to the chain
rather than truncating it, so exploring a direction and backing out never
destroys the work already done.

Pure data with no Streamlit import, so the chain is testable without a
runtime."
```

---

## Task 5: Guidance for the new failures

**Files:**
- Modify: `colouring_factory/guidance.py`
- Modify: `tests/test_guidance.py`

**Interfaces:**
- Produces: guidance entries for `edit_unsupported` and `edit_failed`.

- [ ] **Step 1: Add the entries**

The existing `test_every_generator_error_code_has_guidance` scans `generators.py` for raised codes, so it already fails once Task 2 lands. Add to `_ENTRIES` in `colouring_factory/guidance.py`:

```python
    "edit_unsupported": Guidance(
        title="This provider cannot change a picture",
        cause="The chosen provider can draw a new picture but not modify an existing one.",
        fix="Switch provider, or draw a new picture with the change described in the idea.",
        control=_SETTINGS,
        action_label="Choose a provider",
    ),
    "edit_failed": Guidance(
        title="The change could not be made",
        cause="The provider accepted the request but returned no changed picture.",
        fix="Try describing the change in fewer, plainer words. The picture you had is unchanged.",
        control="Make a change, beneath the picture",
    ),
```

- [ ] **Step 2: Add the test**

Append to `tests/test_guidance.py`:

```python
def test_the_refinement_failures_have_guidance() -> None:
    for code in ("edit_unsupported", "edit_failed"):
        entry = guidance_for(code)
        assert entry.title.strip()
        assert entry.fix.strip()
        assert entry.control.strip()


def test_a_failed_refinement_reassures_that_nothing_was_lost() -> None:
    # A failed edit costs an image charge; the user should not also fear that
    # the picture they had is gone.
    assert "unchanged" in guidance_for("edit_failed").fix.lower()
```

- [ ] **Step 3: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass, including the scan test that every raised code has an entry.

- [ ] **Step 4: Commit**

```bash
git add colouring_factory/guidance.py tests/test_guidance.py
git commit -m "Explain the two ways a refinement can fail

A provider that cannot edit, and one that accepts the request but returns
nothing. The second says plainly that the picture already on screen is
unchanged, because a failed edit costs a full image charge and the user
should not also have to wonder whether the original survived."
```

---

## Task 6: The refine control and version strip

**Files:**
- Modify: `app.py`
- Create: `tests/test_app_refine.py`

**Interfaces:**
- Consumes: everything from Tasks 1 to 5.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add the state and the renderer**

In `app.py`, add `"doodle_versions": (), "current_version": 0` to the defaults in `_initialise_state`, and import `history` plus `refine_with_provider` and `build_refinement_prompt` in the same edit as their first use.

Add a renderer beside the other helpers:

```python
def _render_refine_controls(*, key_prefix: str) -> None:
    """The refine box and the version strip beneath a picture."""

    chain = st.session_state.get("doodle_versions", ())
    if not chain:
        return

    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)

    if len(chain) > 1:
        st.caption(f"{len(chain)} versions drawn in this chain")
        strip = st.columns(min(len(chain), 6))
        for index, version in enumerate(chain):
            with strip[index % len(strip)]:
                st.image(version.artwork.image_bytes, width="stretch")
                label = version.instruction or "Original"
                if index == st.session_state.current_version:
                    st.caption(f"**{label}** — showing")
                else:
                    st.caption(label)
                    if st.button(
                        "Go back to this",
                        key=f"{key_prefix}_pick_{index}",
                        width="stretch",
                        icon=":material/history:",
                    ):
                        st.session_state.current_version = index
                        current = chain[index].artwork
                        _set_current_artwork(
                            current.image_bytes,
                            title=st.session_state.current_title,
                            metadata=st.session_state.current_metadata,
                        )
                        st.rerun()

    with st.form(f"{key_prefix}_refine", clear_on_submit=True):
        instruction = st.text_input(
            "Make a change",
            placeholder="Give the dinosaur a party hat",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button(
            "Change it", type="primary", width="stretch", icon=":material/edit:"
        )

    st.caption(
        "The whole picture is redrawn, so parts you did not ask about may shift "
        "a little. Each change costs one generation."
    )

    if not submitted:
        return
    if not instruction.strip():
        _show_guidance("missing_prompt")
        return
    if not api_key:
        _show_guidance("missing_key")
        return

    base = chain[st.session_state.current_version]
    settings = load_settings()
    model = str(settings.get(f"{provider_id}_model", spec.default_model))
    if model not in spec.models:
        model = spec.default_model

    try:
        prompt = build_refinement_prompt(instruction)
        with st.spinner("Making that change…"):
            artwork = refine_with_provider(
                provider_id=provider_id,
                api_key=api_key,
                image_bytes=base.artwork.image_bytes,
                prompt=prompt,
                model=model,
                size=spec.portrait_size,
            )
    except GeneratorError as exc:
        # The chain is untouched, so a failed change costs nothing but the call.
        _show_guidance(exc.code, detail=str(exc))
        return
    except ValueError as exc:
        _show_guidance("missing_prompt", detail=str(exc))
        return

    st.session_state.doodle_versions = history.append(
        chain, artwork, instruction, parent=st.session_state.current_version
    )
    st.session_state.current_version = len(st.session_state.doodle_versions) - 1
    _set_current_artwork(
        artwork.image_bytes,
        title=st.session_state.current_title,
        metadata={**st.session_state.current_metadata, "instruction": instruction},
    )
    st.rerun()
```

- [ ] **Step 2: Start a chain whenever artwork is chosen**

In `_set_current_artwork`, leave the chain alone (it is called by the refinement itself). Instead start a chain at the two places a picture is *chosen*: after a successful generation in the studio, and in `_quick_generate`. In both, after `_set_current_artwork(...)`:

```python
    st.session_state.doodle_versions = history.start(art)
    st.session_state.current_version = 0
```

using whichever `GeneratedArtwork` was selected. In the studio's "Use this doodle" button, start a fresh chain from the chosen candidate, since picking a different candidate abandons the previous chain.

- [ ] **Step 3: Replace the old change box on the result screen**

In `_render_first_result`, delete the existing "Make a change" text input and the block that rewrites `generation_idea` and regenerates, and call `_render_refine_controls(key_prefix="result")` in its place.

- [ ] **Step 4: Add it to the studio**

In the create tab, after the processed-image preview in Step 2, call `_render_refine_controls(key_prefix="studio")`.

- [ ] **Step 5: Write the test**

Create `tests/test_app_refine.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from colouring_factory import history
from colouring_factory.models import GeneratedArtwork

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    for variable in ("OPENAI_API_KEY", "GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)


def _art(tag: str) -> GeneratedArtwork:
    return GeneratedArtwork(
        image_bytes=ARTWORK, prompt=tag, provider="OpenAI", model="gpt-image-2"
    )


def _studio_with_chain(chain) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "studio"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["current_title"] = "Test dinosaur"
    at.session_state["current_metadata"] = {"source": "test"}
    at.session_state["doodle_versions"] = chain
    at.session_state["current_version"] = len(chain) - 1
    at.run()
    return at


def test_the_refine_box_appears_once_a_picture_exists() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    assert not at.exception
    labels = [widget.label for widget in at.text_input]
    assert "Make a change" in labels


def test_the_limitation_is_stated_next_to_the_box() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    captions = " ".join(caption.value for caption in at.caption)
    assert "redrawn" in captions
    assert "costs one generation" in captions


def test_submitting_with_no_key_explains_rather_than_crashing() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    for widget in at.text_input:
        if widget.label == "Make a change":
            widget.set_value("give it a hat")
            break
    at.get("form_submit_button")[0].click().run()

    assert not at.exception
    assert any("connected" in error.value.lower() for error in at.error)


def test_the_version_strip_shows_the_chain_and_can_step_back() -> None:
    chain = history.start(_art("original"))
    chain = history.append(chain, _art("hatted"), "add a hat", parent=0)
    at = _studio_with_chain(chain)

    captions = " ".join(caption.value for caption in at.caption)
    assert "2 versions" in captions
    assert "add a hat" in captions

    back = [b for b in at.button if "Go back" in b.label]
    assert back, "no way to return to an earlier version"

    # Click it, do not merely assert it renders.
    back[0].click().run()
    assert not at.exception
    assert at.session_state["current_version"] == 0


def test_a_single_version_shows_no_strip() -> None:
    at = _studio_with_chain(history.start(_art("original")))
    assert not [b for b in at.button if "Go back" in b.label]
```

- [ ] **Step 6: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all pass.

- [ ] **Step 7: Prove the click tests can fail**

Temporarily change `_render_refine_controls` so the "Go back to this" button renders but its body does nothing, run `test_the_version_strip_shows_the_chain_and_can_step_back`, confirm it FAILS, then restore. A button test that passes either way is worth nothing.

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_app_refine.py
git commit -m "Refine a picture in place, with the versions kept beside it

The result screen's Make a change box rewrote the original idea and drew
a new picture from scratch. Since alternatives started coming back
genuinely different, that no longer returned anything like what was on
screen. It now changes the picture itself.

Every version stays in a strip beneath, captioned with what was asked
for, and going back to an earlier one adds to the chain rather than
truncating it. The count is shown because each change costs a full
generation, and the redrawing limitation is stated next to the box so
drift reads as expected rather than broken.

The step-back button is clicked in its test, and that test confirmed to
fail when the button is left inert."
```

---

## Task 7: Document it

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the section**

After the `### Alternatives` section:

```markdown
### Changing a picture

Beneath any generated picture is a **Make a change** box. Describe what you want
different — "give the dinosaur a party hat", "move the fire engine away from the
edge" — and Doodle changes that picture rather than drawing a new one from your
original words.

Every version is kept in a strip beneath the picture, captioned with what you
asked for. Going back to an earlier version does not delete the ones after it, so
exploring an idea and changing your mind costs nothing but the drawing itself.

Two things to expect. The whole picture is redrawn each time, so parts you did not
ask about may shift a little; this is how all three providers work without a brush
mask, and is not a fault. And each change costs one image generation, so the
version count is shown beside the box.

Refining works on generated pictures. Uploaded and demo artwork can be laid out and
printed but not changed, because Doodle does not know which model drew them.
```

- [ ] **Step 2: Run the full suite and commit**

```bash
git add README.md
git commit -m "Document refining a picture

Says plainly that the whole picture is redrawn so unasked-for parts may
shift, that each change costs a generation, and that uploaded artwork
cannot be refined because Doodle does not know which model drew it."
```

---

## Verification before the PR leaves draft

- [ ] `.venv/bin/python -m pytest` green, output pasted into the PR
- [ ] Every new button clicked in a test, and at least one such test confirmed to fail when its handler is removed
- [ ] `git fetch origin && git rev-list --count HEAD..origin/main` returns 0 immediately before opening and before merging — two pull requests crossing turned `main` red on 2026-08-30
- [ ] The spec's non-goals have not been quietly implemented
- [ ] `gh pr ready`
