# Your characters — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save a person, toy or character once, then draw any of them into any colouring page, at full facial fidelity, printable as an A4 sheet or a badge.

**Architecture:** A new pure module holds the cast on disk. The existing image-edit call gains a second, separate argument for reference pictures, with each provider declaring how many it takes as data on its spec. Everything the feature produces enters the ordinary artwork lifecycle through `_adopt_artwork`, so the studio, the circle sheet, the badge preview and custom page sizes apply for free.

**Tech Stack:** Python 3.11+, Streamlit 1.62, Pillow 12.3, the `openai` package for OpenAI and hand-rolled `urllib` for Gemini and Recraft, pytest with `streamlit.testing.v1.AppTest`.

**Spec:** `docs/superpowers/specs/2026-08-30-doodle-characters-design.md`

## Global Constraints

- **British English, sentence case** on every label, button, heading and tab. Not Title Case.
- **No emoji anywhere in `app.py` string literals** except `page_icon`. No typed glyph icons (`←↻♡✓`); use `icon=":material/name:"`.
- **New proper nouns must be added to the allow-list** in `tests/test_ui_conventions.py` or the sentence-case rule fails: currently `{A4, AI, API, Doodle, Gemini, Google, Mac, OpenAI, PDF, PNG, Recraft, Studio, Enter}`.
- **`app.py` only wires.** All logic lives in `colouring_factory/` modules with no `streamlit` import and their own tests.
- **Provider capability is data on `ProviderSpec`**, never `if provider == "..."` in the interface.
- **Every `GeneratorError` code needs a `guidance.py` entry** with title, cause, fix and control.
- **One new runtime dependency is permitted:** `pillow-heif`. No others. Gemini and Recraft keep using `urllib.request` and the hand-rolled multipart encoder; do not add `requests`.
- **No test makes a network call or spends money.**
- **Every new button must be clicked in a test** and its effect asserted, never merely asserted to exist.
- **Anything a user sees is asserted through `AppTest`**, never through the hand-written fake Streamlit in `tests/test_app_smoke.py`.
- **Commit trailers:** no `Co-Authored-By` line, no "Generated with" footer. The author is already `Milo Garth`.
- **Baseline:** 274 tests pass on `9a2ade2`. `pyproject.toml` already sets `addopts = "-q"`, so run `.venv/bin/python -m pytest` with **no** `-q` flag or the count is swallowed.

## File structure

| File | Responsibility |
|---|---|
| `colouring_factory/photos.py` (new) | Turn an uploaded photograph into a bare, upright, size-capped PNG with no metadata. |
| `colouring_factory/characters.py` (new) | The cast on disk: save, list, load, delete. Knows nothing about drawing. |
| `colouring_factory/providers.py` | Gains `max_reference_images` on `ProviderSpec`. |
| `colouring_factory/generators.py` | Gains `reference_images` on the four refine functions, plus the capacity check and the `photo_declined` remap. |
| `colouring_factory/prompts.py` | Gains two builders; loses the imitation rule. |
| `colouring_factory/guidance.py` | Gains two codes; rewords `content`. |
| `app.py` | The characters screen, the homepage picker, the badge strip. Wiring only. |
| `tests/test_photos.py` (new) | Photograph normalisation, including a real GPS block. |
| `tests/test_characters.py` (new) | The store round-tripping and refusing traversal. |
| `tests/test_character_prompts.py` (new) | The three verbatim rules survive prompt building. |
| `tests/test_app_characters.py` (new) | The characters screen and the homepage picker, driven through `AppTest`. |
| `tests/test_app_badge_strip.py` (new) | The badge strip renders and its redraw button works. |

## Task order and why

Tasks 1 and 2 are repairs that must land before anything builds on them: the test guards are blind to the codes and labels this feature adds, and the version chain can point at the wrong picture. Task 3 must precede Task 4's mime work, because normalising every photograph to PNG at the boundary is what makes the `"image/png"` the generators have always asserted into the truth. Task 6's prompts must precede Task 7, which is the first task with something you can use.

---

### Task 1: Widen the two blind test guards

Both guards were proved blind by experiment on 2026-08-30. `tests/test_guidance.py` scans only two modules for error codes, so a new module's codes ship unguarded; a throwaway module raising `code="photo_declined"` passed 15 of 15, while the identical raise added to `generators.py` failed correctly. `tests/test_ui_conventions.py` never looks at a `file_uploader` label, so this feature's uploader would escape the sentence-case and glyph rules entirely.

**Files:**
- Modify: `tests/test_guidance.py:13-26`
- Modify: `tests/test_ui_conventions.py:76-104`
- Modify: `app.py:2118` (the label the widened guard immediately catches)

**Interfaces:**
- Consumes: nothing.
- Produces: `_codes_raised_in(module)` now accepts any module; `_all_labels(at)` covers `file_uploader`, `toggle` and `multiselect`; `_every_screen()` sweeps six screens.

- [ ] **Step 1: Write the failing test — a code raised outside `generators.py` must be caught**

Add to `tests/test_guidance.py`:

```python
def test_every_module_that_raises_a_code_is_scanned() -> None:
    """A new module's codes must be guarded too.

    On 2026-08-30 a module raising an unguarded code passed this file
    completely, because only two modules were ever scanned by name.
    """

    scanned = _every_raisable_code()
    # app.py raises billing, missing_prompt and missing_key and was never scanned.
    assert {"billing", "missing_prompt", "missing_key"} <= scanned
    missing = sorted(code for code in scanned if code not in GUIDANCE_CODES)
    assert not missing, f"no guidance for: {missing}"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_guidance.py -v`
Expected: FAIL with `NameError: name '_every_raisable_code' is not defined`

- [ ] **Step 3: Implement the widened scan**

Replace `_codes_raised_in` in `tests/test_guidance.py` with a package walk. Read the source as text rather than importing `app`, because importing `app` executes the Streamlit script:

```python
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CODE_PATTERN = re.compile(r'code="([a-z_]+)"')


def _codes_raised_in_source(source: str) -> set[str]:
    return set(CODE_PATTERN.findall(source))


def _every_raisable_code() -> set[str]:
    """Every error code raised anywhere in the project.

    Reading the files as text rather than importing them keeps app.py out of
    the import path: importing it runs the Streamlit script.
    """

    paths = sorted((PROJECT_ROOT / "colouring_factory").glob("*.py"))
    paths.append(PROJECT_ROOT / "app.py")
    codes: set[str] = set()
    for path in paths:
        codes |= _codes_raised_in_source(path.read_text(encoding="utf-8"))
    return codes
```

Keep the two existing tests working by pointing them at the new helper rather than deleting them.

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_guidance.py -v`
Expected: PASS. If it fails naming a code, that code genuinely lacks guidance — add the entry rather than narrowing the scan.

- [ ] **Step 5: Write the failing test for the label guard**

Add to `tests/test_ui_conventions.py`:

```python
def test_uploader_and_toggle_labels_are_checked() -> None:
    """The label sweep must see every widget family a screen can hold.

    On 2026-08-30 _all_labels iterated eleven families and missed
    file_uploader, toggle and multiselect, so an uploader's label was
    subject to neither the glyph rule nor the sentence-case rule.
    """

    labels = _all_labels(_studio())
    assert any("upload" in label.lower() for label in labels)
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_ui_conventions.py::test_uploader_and_toggle_labels_are_checked -v`
Expected: FAIL, because no uploader label is collected.

- [ ] **Step 7: Widen `_all_labels` and `_every_screen`**

In `tests/test_ui_conventions.py`, add three families to the tuple inside `_all_labels` (do **not** add `pills`; `at.get("pills")` returns nothing on Streamlit 1.62):

```python
        at.get("file_uploader"),
        at.get("toggle"),
        at.get("multiselect"),
```

And add the two unswept screens to `_every_screen()`, whose docstring already claims six:

```python
        _library(),
        _generate(),
```

with helpers following the existing `_studio()` pattern:

```python
def _library() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "library"
    at.session_state["library_return"] = "home"
    at.run()
    return at


def _generate() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["quick_mode"] = "demo"
    at.run()
    return at
```

- [ ] **Step 8: Run the whole convention file and fix what it now catches**

Run: `.venv/bin/python -m pytest tests/test_ui_conventions.py -v`
Expected: the sentence-case rule now fails on `app.py:2118`, `"Upload PNG, JPG or WebP artwork"`, because `JPG` and `WebP` are capitalised and not in the allow-list. Change the label to sentence case rather than widening the allow-list, since it reads better anyway:

```python
            "Upload a picture",
```

and move the format list into the help text beside it:

```python
            help="PNG, JPG or WebP.",
```

- [ ] **Step 9: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: 277 passed (274 plus the three new tests), 0 failed.

- [ ] **Step 10: Commit**

```bash
git add tests/test_guidance.py tests/test_ui_conventions.py app.py
git commit -m "Make the guidance and label guards see every module and widget"
```

---

### Task 2: Stop the version chain surviving a new doodle

Proved on 2026-08-30: `_start_new_doodle` clears 21 session keys but not `doodle_versions` or `current_version`, and the demo branch of `_quick_generate` calls `_set_current_artwork` without `_start_version_chain`. After a demo doodle drawn following an AI one, the change box acts on the earlier picture. The badge redraw reads the same chain, so this is fixed before anything builds on it.

**Files:**
- Modify: `app.py:341-363` (`_start_new_doodle`)
- Modify: `app.py` demo branch of `_quick_generate` (around 1437-1455)
- Modify: `app.py:1696` (`_render_first_result`)
- Test: `tests/test_refine.py`

**Interfaces:**
- Consumes: nothing.
- Produces: a guarantee that `st.session_state.doodle_versions` always describes the picture currently on screen, relied on by Task 9's badge redraw.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_refine.py`:

```python
def test_a_new_doodle_leaves_no_version_chain_behind() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = ARTWORK
    at.session_state["quick_pdf"] = b"%PDF-1.4 test"
    at.session_state["doodle_versions"] = history.start(
        GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="test", model="m"
        )
    )
    at.session_state["current_version"] = 0
    at.run()

    for button in at.button:
        if button.label == "New doodle":
            button.click().run()
            break
    else:
        raise AssertionError("New doodle button not found")

    assert at.session_state["doodle_versions"] == ()
    assert at.session_state["current_version"] == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_refine.py::test_a_new_doodle_leaves_no_version_chain_behind -v`
Expected: FAIL, `assert (Version(...),) == ()`

- [ ] **Step 3: Clear both keys in `_start_new_doodle`**

Add to the block of assignments in `app.py:341-363`, keeping the existing comment style:

```python
    # A chain left behind points the change box at the previous picture, so a
    # refinement quietly edits a doodle that is no longer on screen.
    st.session_state.doodle_versions = ()
    st.session_state.current_version = 0
```

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_refine.py::test_a_new_doodle_leaves_no_version_chain_behind -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for the demo path**

```python
def test_a_demo_doodle_starts_its_own_version_chain() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "generate"
    at.session_state["quick_mode"] = "demo"
    at.session_state["generation_idea"] = "a blue dinosaur"
    at.session_state["doodle_versions"] = history.start(
        GeneratedArtwork(
            image_bytes=OTHER, prompt="earlier", provider="test", model="m"
        )
    )
    at.run()

    chain = at.session_state["doodle_versions"]
    assert len(chain) == 1
    assert chain[0].artwork.image_bytes == at.session_state["current_raw"]
```

- [ ] **Step 6: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_refine.py::test_a_demo_doodle_starts_its_own_version_chain -v`
Expected: FAIL, the chain still holds the earlier picture.

- [ ] **Step 7: Start a chain on the demo path**

In the demo branch of `_quick_generate`, after `_set_current_artwork(...)` and before `st.session_state.candidates = []`, wrap the sample in an artwork and start the chain:

```python
        sample = GeneratedArtwork(
            image_bytes=raw,
            prompt=idea,
            provider="Built-in sample",
            model=demo_name,
            metadata={"sample": demo_name, "concept": idea},
        )
        _start_version_chain(sample)
```

- [ ] **Step 8: Write the failing test for the result screen's missing guard**

```python
def test_the_result_screen_survives_unprepared_outputs() -> None:
    """Reaching the result screen without preparing outputs must not crash.

    _render_first_result hands quick_processed straight to sha256, so a None
    raises TypeError and the whole page dies rather than showing anything.
    """

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "result"
    at.session_state["current_raw"] = ARTWORK
    at.session_state["quick_processed"] = None
    at.session_state["quick_pdf"] = None
    at.run()

    assert not at.exception
```

- [ ] **Step 9: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_refine.py::test_the_result_screen_survives_unprepared_outputs -v`
Expected: FAIL with `TypeError` from `hashlib.sha256(None)`

- [ ] **Step 10: Guard the renderer**

At the top of the body of `_render_first_result`, after the top bar is drawn, return early when there is nothing prepared:

```python
    processed = st.session_state.get("quick_processed")
    if not processed:
        # Reaching here with nothing prepared is a routing mistake rather than
        # a user error, so say so plainly instead of dying on a None.
        st.error("That doodle is not ready yet. Draw it again.")
        return
```

and use the local `processed` for the calls that followed.

- [ ] **Step 11: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: 280 passed, 0 failed.

- [ ] **Step 12: Commit**

```bash
git add app.py tests/test_refine.py
git commit -m "Keep the version chain pointing at the doodle on screen"
```

---

### Task 3: Normalise an uploaded photograph

The implementation and its tests were written and run on 2026-08-30 and are reproduced here verbatim. One Pillow 12 detail cost a first run: the RATIONAL writer no longer accepts `(numerator, denominator)` tuples, so GPS coordinates in the fixture must be `IFDRational` instances.

**Files:**
- Create: `colouring_factory/photos.py`
- Create: `tests/test_photos.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: `prepare_photo(photo_bytes: bytes, max_edge: int = 1536) -> bytes`, returning PNG bytes. Raises `ValueError` on empty or unreadable input. Used by Task 5's store and Task 7's upload screen.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_photos.py`. The first test exists so the stripping test cannot pass vacuously:

```python
from io import BytesIO

import pytest
from PIL import Image
from PIL.TiffImagePlugin import IFDRational

from colouring_factory.photos import prepare_photo

# 51°30'N, 0°7'W — the coordinates a London phone photo would carry. Pillow 12
# encodes a RATIONAL from an IFDRational, not from a (numerator, denominator)
# tuple, so the fixture builds them explicitly.
GPS_LATITUDE = (IFDRational(51), IFDRational(30), IFDRational(0))
GPS_LONGITUDE = (IFDRational(0), IFDRational(7), IFDRational(0))

ORIENTATION = 0x0112
MAKE = 0x010F
GPS_IFD_POINTER = 0x8825


def _photo_with_gps(size=(60, 40), orientation=6) -> bytes:
    """A real JPEG carrying a populated GPS IFD, a Make tag and an orientation."""

    image = Image.new("RGB", size, (180, 90, 40))
    exif = Image.Exif()
    exif[MAKE] = "Apple"
    exif[0x0110] = "iPhone 15 Pro"
    exif[ORIENTATION] = orientation
    exif[GPS_IFD_POINTER] = {
        0: b"\x02\x03\x00\x00",
        1: "N",
        2: GPS_LATITUDE,
        3: "W",
        4: GPS_LONGITUDE,
        5: 0,
        6: IFDRational(12),
    }
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


def test_the_fixture_really_carries_gps_and_a_make_tag() -> None:
    original = Image.open(BytesIO(_photo_with_gps()))
    exif = original.getexif()
    assert exif[MAKE] == "Apple"
    assert exif[ORIENTATION] == 6
    gps = exif.get_ifd(GPS_IFD_POINTER)
    assert gps[2] == GPS_LATITUDE
    assert b"Apple" in _photo_with_gps()


def test_gps_and_every_other_exif_tag_are_gone() -> None:
    prepared = prepare_photo(_photo_with_gps())
    reopened = Image.open(BytesIO(prepared))

    assert dict(reopened.getexif()) == {}
    assert reopened.getexif().get_ifd(GPS_IFD_POINTER) == {}
    assert "exif" not in reopened.info
    assert reopened.info.get("icc_profile") is None
    # Belt and braces against a tag surviving in a chunk getexif does not read.
    assert b"Apple" not in prepared
    assert b"GPS" not in prepared


def test_the_output_really_is_a_png() -> None:
    assert Image.open(BytesIO(prepare_photo(_photo_with_gps()))).format == "PNG"


def test_orientation_six_is_baked_into_the_pixels() -> None:
    # A 60x40 landscape original with orientation 6 is a portrait photograph
    # held sideways, so the stored pixels must come back 40x60.
    prepared = prepare_photo(_photo_with_gps(size=(60, 40), orientation=6))
    assert Image.open(BytesIO(prepared)).size == (40, 60)


def test_a_large_photo_is_capped_on_its_long_edge() -> None:
    big = Image.new("RGB", (4000, 3000), "red")
    buffer = BytesIO()
    big.save(buffer, format="JPEG")
    assert Image.open(BytesIO(prepare_photo(buffer.getvalue()))).size == (1536, 1152)


def test_a_small_photo_is_not_upscaled() -> None:
    small = Image.new("RGB", (80, 60), "red")
    buffer = BytesIO()
    small.save(buffer, format="PNG")
    assert Image.open(BytesIO(prepare_photo(buffer.getvalue()))).size == (80, 60)


def test_transparency_is_flattened_onto_white() -> None:
    transparent = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    buffer = BytesIO()
    transparent.save(buffer, format="PNG")
    flattened = Image.open(BytesIO(prepare_photo(buffer.getvalue())))
    assert flattened.mode == "RGB"
    assert flattened.getpixel((5, 5)) == (255, 255, 255)


def test_empty_and_unreadable_input_are_refused() -> None:
    with pytest.raises(ValueError):
        prepare_photo(b"")
    with pytest.raises(ValueError):
        prepare_photo(b"this is not a picture")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_photos.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'colouring_factory.photos'`

- [ ] **Step 3: Write the module**

Create `colouring_factory/photos.py`:

```python
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

# A phone photograph carries the camera make, the capture time and, very often,
# the exact coordinates of a family home. None of that belongs in a file handed
# to a third-party image API, so every reference photograph is re-encoded from
# pixels alone before it is stored.
MAX_PHOTO_EDGE_PX = 1536


def prepare_photo(photo_bytes: bytes, max_edge: int = MAX_PHOTO_EDGE_PX) -> bytes:
    """Normalise an uploaded reference photograph into a bare PNG.

    Applies the EXIF orientation so a portrait phone photo is not stored on its
    side, discards every metadata block including GPS coordinates, caps the long
    edge so a 48-megapixel original does not become a 60 MB upload, and re-encodes
    as PNG so the "image/png" the generators send is the truth.
    """

    if not photo_bytes:
        raise ValueError("No photograph was supplied.")
    if max_edge < 1:
        raise ValueError("The pixel cap must be at least one pixel.")

    try:
        with Image.open(BytesIO(photo_bytes)) as source:
            source.load()
            # Rotation first: the orientation tag is about to be thrown away with
            # the rest of the metadata, so it has to be baked into the pixels
            # while it is still readable.
            rotated = ImageOps.exif_transpose(source) or source
            flattened = _flatten_to_white(rotated)
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("That file could not be read as a photograph.") from exc

    if max(flattened.size) > max_edge:
        flattened.thumbnail((max_edge, max_edge), Image.LANCZOS)

    # Copying the pixels into a freshly created image is what actually strips the
    # metadata: Image.new starts with an empty info dictionary, so there is no
    # EXIF block, no ICC profile and no PNG text chunk left for the encoder.
    stripped = Image.new("RGB", flattened.size)
    stripped.paste(flattened)

    output = BytesIO()
    stripped.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _flatten_to_white(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        return background.convert("RGB")
    return image.convert("RGB")
```

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_photos.py -v`
Expected: 9 passed

- [ ] **Step 5: Add HEIC support**

Photographs straight off an iPhone are HEIC and Pillow 12.3 has no decoder for them, so the file picker greys them out with no explanation. Add to `requirements.txt`, after `Pillow`:

```
pillow-heif>=0.18,<1
```

Then register the opener once, at the bottom of the import block in `colouring_factory/photos.py`:

```python
# Photographs straight off an iPhone are HEIC, which Pillow cannot open on its
# own. This is the one runtime dependency the characters feature adds; a photo
# feature that cannot read the format most family photographs are in is broken
# on arrival.
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:  # pragma: no cover - only in an incomplete installation.
    pass
```

- [ ] **Step 6: Install and prove it opens a HEIC**

Run: `.venv/bin/pip install -r requirements.txt`
Then add this test to `tests/test_photos.py`:

```python
def test_a_heic_photograph_can_be_read() -> None:
    pillow_heif = pytest.importorskip("pillow_heif")
    source = Image.new("RGB", (120, 80), (200, 30, 40))
    buffer = BytesIO()
    pillow_heif.from_pillow(source).save(buffer, format="HEIF", quality=60)
    prepared = prepare_photo(buffer.getvalue())
    assert Image.open(BytesIO(prepared)).size == (120, 80)
```

Run: `.venv/bin/python -m pytest tests/test_photos.py -v`
Expected: 10 passed

- [ ] **Step 7: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: 290 passed, 0 failed.

- [ ] **Step 8: Commit**

```bash
git add colouring_factory/photos.py tests/test_photos.py requirements.txt
git commit -m "Read a photograph from any phone, and store none of its metadata"
```

---

### Task 4: Let a drawing carry reference pictures

`refine_with_provider` already means "prompt plus picture in, picture out" on all three providers. It gains a second, separate argument. The separation matters beyond tidiness: it is what lets the dispatcher tell a refusal that carried someone's photograph apart from a refusal of the wording, which is what makes the error message truthful.

**Files:**
- Modify: `colouring_factory/providers.py` (the `ProviderSpec` dataclass and all three entries)
- Modify: `colouring_factory/generators.py` (`refine_with_openai`, `refine_with_google`, `refine_with_recraft`, `refine_with_provider`)
- Modify: `colouring_factory/guidance.py`
- Test: `tests/test_providers.py`, `tests/test_openai_wire.py`, `tests/test_generators_google.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ProviderSpec.max_reference_images: int` — OpenAI 16, Google 4, Recraft 0.
  - `refine_with_provider(..., reference_images: Sequence[bytes] = ())` with `image_bytes: bytes | None = None`.
  - Codes `no_reference_support`, `too_many_references`, `photo_declined`.

Used by Tasks 6, 7, 8 and 9.

- [ ] **Step 1: Write the failing test for the capability field**

Add to `tests/test_providers.py`:

```python
def test_every_provider_declares_how_many_pictures_it_can_look_at() -> None:
    """Capability is data on the spec, never a branch on a provider's name.

    OpenAI documents sixteen input pictures for the GPT image models. Google
    documents ten object plus four character references for its default image
    model. Recraft's imageToImage takes one multipart field called "image", so
    it cannot carry a cast at all.
    """

    assert PROVIDERS["openai"].max_reference_images == 16
    assert PROVIDERS["google"].max_reference_images == 4
    assert PROVIDERS["recraft"].max_reference_images == 0
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: FAIL, `AttributeError: 'ProviderSpec' object has no attribute 'max_reference_images'`

- [ ] **Step 3: Add the field**

In `colouring_factory/providers.py`, add to the frozen dataclass beneath `edit_closeness`, following the module's habit of explaining a capability in a comment rather than in the interface:

```python
    # How many reference pictures the provider will look at in one request.
    # Zero means it cannot draw from a photograph at all, so the interface never
    # offers the control rather than offering one that fails. Recraft's
    # imageToImage takes a single multipart field named "image", and a dict
    # cannot hold two keys of that name.
    max_reference_images: int = 0
```

Set `max_reference_images=16` on OpenAI, `max_reference_images=4` on Google, and leave Recraft at the default, with a one-line comment on each recording where the number came from.

- [ ] **Step 4: Run it to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_providers.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing tests for the OpenAI multipart body**

Add to `tests/test_openai_wire.py`, copying the fake-client capture pattern already in that file:

```python
def test_two_reference_pictures_become_two_image_parts() -> None:
    captured = _capture(lambda: refine_with_openai(
        api_key="sk-test",
        prompt="draw them on a beach",
        reference_images=(b"first-picture", b"second-picture"),
        model="gpt-image-2",
    ))
    assert isinstance(captured["image"], list)
    assert len(captured["image"]) == 2


def test_one_picture_stays_a_single_part() -> None:
    """A single picture keeps the old wire form.

    Sending a one-element list changes the multipart field from image to
    image[], and there is no reason to move every existing call onto a
    different shape.
    """

    captured = _capture(lambda: refine_with_openai(
        api_key="sk-test", image_bytes=b"one", prompt="change it"
    ))
    assert not isinstance(captured["image"], list)
```

- [ ] **Step 6: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_openai_wire.py -v`
Expected: FAIL, `TypeError: refine_with_openai() got an unexpected keyword argument 'reference_images'`

- [ ] **Step 7: Implement the OpenAI change**

In `refine_with_openai`, make `image_bytes: bytes | None = None`, add `reference_images: Sequence[bytes] = ()`, and replace the hardcoded tuple in `request_kwargs`:

```python
    pictures = [*([image_bytes] if image_bytes else []), *reference_images]
    if not pictures:
        raise ValueError("At least one picture is required.")

    def _part(index: int, payload: bytes) -> tuple[str, BytesIO, str]:
        return (f"doodle{index}.png", BytesIO(payload), _mime_for(payload))

    request_kwargs["image"] = (
        _part(0, pictures[0])
        if len(pictures) == 1
        else [_part(index, payload) for index, payload in enumerate(pictures)]
    )
```

Leave `input_fidelity` exactly as it is. `openai_supports_input_fidelity` already returns `False` for `gpt-image-2`, which rejects the argument outright, and that model works at high input fidelity regardless.

- [ ] **Step 8: Add the format sniffer**

Beside the other helpers near the top of `colouring_factory/generators.py`:

```python
def _mime_for(payload: bytes) -> str:
    """Name the format from the bytes rather than asserting one.

    Every picture Doodle used to send was one it had drawn, so the hardcoded
    "image/png" was harmless. A reference photograph is usually a JPEG.
    """

    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if payload[:4] == b"RIFF" and payload[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"
```

Use it at the OpenAI mask part and the Recraft multipart body as well.

- [ ] **Step 9: Run to verify, then write the Gemini test**

Run: `.venv/bin/python -m pytest tests/test_openai_wire.py -v` → PASS.

Add to `tests/test_generators_google.py`, using that file's existing `fake_urlopen` capture:

```python
def test_each_reference_picture_becomes_its_own_image_block() -> None:
    captured = _capture_body(lambda: refine_with_google(
        api_key="key",
        prompt="draw them on a beach",
        reference_images=(PNG_BYTES, JPEG_BYTES),
    ))

    blocks = captured["input"]
    assert [block["type"] for block in blocks] == ["text", "image", "image"]
    assert blocks[1]["mime_type"] == "image/png"
    assert blocks[2]["mime_type"] == "image/jpeg"
```

- [ ] **Step 10: Run it to verify it fails, then implement**

Run: `.venv/bin/python -m pytest tests/test_generators_google.py -v` → FAIL on the unexpected keyword.

Build the Gemini `input` from a list rather than a two-element literal:

```python
    "input": [
        {"type": "text", "text": instruction},
        *(
            {
                "type": "image",
                "mime_type": _mime_for(payload),
                "data": base64.b64encode(payload).decode("ascii"),
            }
            for payload in pictures
        ),
    ],
```

Run again: PASS.

- [ ] **Step 11: Decide Recraft in the dispatcher, not the adapter**

`refine_with_recraft` gains the keyword and uses `pictures[0]`, with a comment recording that its multipart helper keys files by name so two cannot both be called `image`. The decision that Recraft cannot carry a cast is taken in `refine_with_provider` from the spec, before any HTTP:

```python
    if reference_images and spec.max_reference_images < 1:
        raise GeneratorError(
            f"{spec.label} cannot draw from a picture of someone.",
            provider=spec.label,
            code="no_reference_support",
        )
    if reference_images and len(reference_images) > spec.max_reference_images:
        raise GeneratorError(
            f"{spec.label} can look at {spec.max_reference_images} pictures at "
            "a time. Choose fewer characters.",
            provider=spec.label,
            code="too_many_references",
        )
```

- [ ] **Step 12: Write the failing test for the refusal remap**

```python
def test_a_refusal_that_carried_a_photograph_gets_its_own_code() -> None:
    """A refused photograph must not be explained as a wording problem.

    _normalise_error classifies on the response text alone and cannot know a
    picture was attached, so the only layer that can tell is the one that
    attached it.
    """

    with pytest.raises(GeneratorError) as raised:
        refine_with_provider(
            provider_id="openai",
            api_key="sk-test",
            prompt="draw her on a beach",
            reference_images=(b"photo",),
            model="gpt-image-2",
            size="1024x1536",
        )
    assert raised.value.code == "photo_declined"


def test_a_refusal_with_no_picture_stays_a_content_refusal() -> None:
    """Doodle's own malformed Google requests also reach code="content".

    Translating every one of them into a declined photograph would blame the
    user's picture for Doodle's bug.
    """

    with pytest.raises(GeneratorError) as raised:
        refine_with_provider(
            provider_id="openai",
            api_key="sk-test",
            image_bytes=b"line art",
            prompt="add a hat",
            model="gpt-image-2",
            size="1024x1536",
        )
    assert raised.value.code == "content"
```

Both need the fake OpenAI client to raise a content-policy refusal; copy the stub from `tests/test_refine.py`.

- [ ] **Step 13: Implement the remap**

Wrap the dispatch in `refine_with_provider`:

```python
    try:
        return _dispatch_refinement(...)
    except GeneratorError as error:
        if error.code == "content" and reference_images:
            raise GeneratorError(
                f"{spec.label} would not draw from that picture.",
                provider=spec.label,
                code="photo_declined",
                status_code=error.status_code,
            ) from error
        raise
```

Extract the existing three-branch dispatch into `_dispatch_refinement` so the `try` wraps one call rather than the whole body.

- [ ] **Step 14: Add the three guidance entries**

In `colouring_factory/guidance.py`. Task 1's widened scan fails the suite until these exist:

```python
    "photo_declined": Guidance(
        title="The provider would not draw from that picture",
        cause=(
            "The drawing service ran its own check on the picture and declined "
            "it. Doodle does not know which part it objected to."
        ),
        fix=(
            "Try a different picture of the same character, or untick them and "
            "let the written description do the work."
        ),
        control="Your characters, on the homepage",
    ),
    "no_reference_support": Guidance(
        title="This drawing service cannot draw from a picture",
        cause="Recraft accepts one picture per request, so it cannot carry a cast.",
        fix="Connect OpenAI or Google Gemini to draw your characters.",
        control="Change image provider, on the result screen",
    ),
    "too_many_references": Guidance(
        title="That is more characters than this service will look at",
        cause="Each drawing service has its own limit on reference pictures.",
        fix="Untick some characters and draw again.",
        control="Your characters, on the homepage",
    ),
```

- [ ] **Step 15: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`
Expected: all green.

```bash
git add colouring_factory/providers.py colouring_factory/generators.py colouring_factory/guidance.py tests/test_providers.py tests/test_openai_wire.py tests/test_generators_google.py tests/test_refine.py
git commit -m "Draw from several reference pictures, where the provider allows it"
```

---

### Task 5: The character store

**Files:**
- Create: `colouring_factory/characters.py`
- Create: `tests/test_characters.py`

**Interfaces:**
- Consumes: `data_root` from `colouring_factory/storage.py`.
- Produces:
  - `Character` frozen dataclass with `id`, `name`, `kind`, `marks`, `created_at`, all `str`.
  - `CHARACTER_KINDS = ("person", "toy", "character")`
  - `characters_root() -> Path`
  - `save_character(*, photo: bytes, portrait: bytes, name: str, kind: str, marks: str) -> str`
  - `list_characters() -> list[Character]` (newest first)
  - `load_character(character_id: str) -> Character`
  - `load_character_image(character_id: str, *, portrait: bool = True) -> bytes`
  - `delete_character(character_id: str) -> None`

Used by Tasks 7 and 8.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_characters.py`. There is no `conftest.py` in this repo by design, so the isolation fixture is copied per file. It must also clear the legacy variable, because `data_root()` reads `COLOURING_FACTORY_DATA_DIR` and it can silently win:

```python
import pytest

from colouring_factory.characters import (
    characters_root,
    delete_character,
    list_characters,
    load_character,
    load_character_image,
    save_character,
)

PHOTO = b"\x89PNG\r\n\x1a\n" + b"photo bytes"
PORTRAIT = b"\x89PNG\r\n\x1a\n" + b"portrait bytes"


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)


def test_a_saved_character_comes_back_whole() -> None:
    character_id = save_character(
        photo=PHOTO,
        portrait=PORTRAIT,
        name="Ida",
        kind="person",
        marks="Curly hair to her shoulders, round glasses.",
    )

    saved = load_character(character_id)
    assert saved.name == "Ida"
    assert saved.kind == "person"
    assert saved.marks == "Curly hair to her shoulders, round glasses."
    assert load_character_image(character_id) == PORTRAIT
    assert load_character_image(character_id, portrait=False) == PHOTO


def test_characters_come_back_newest_first() -> None:
    for name in ("Ida", "Bo", "Bear"):
        save_character(
            photo=PHOTO, portrait=PORTRAIT, name=name, kind="person", marks="x"
        )
    assert [c.name for c in list_characters()] == ["Bear", "Bo", "Ida"]


def test_a_nameless_character_is_refused() -> None:
    with pytest.raises(ValueError):
        save_character(
            photo=PHOTO, portrait=PORTRAIT, name="   ", kind="person", marks="x"
        )


def test_an_unknown_kind_is_refused() -> None:
    with pytest.raises(ValueError):
        save_character(
            photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="dragon", marks="x"
        )


def test_a_folder_missing_its_metadata_is_skipped_rather_than_fatal() -> None:
    save_character(photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks="x")
    (characters_root() / "half-written").mkdir()
    assert [c.name for c in list_characters()] == ["Ida"]


def test_deleting_removes_the_only_copy() -> None:
    character_id = save_character(
        photo=PHOTO, portrait=PORTRAIT, name="Ida", kind="person", marks="x"
    )
    delete_character(character_id)
    assert list_characters() == []
    assert not (characters_root() / character_id).exists()


def test_a_traversing_id_is_refused() -> None:
    with pytest.raises(ValueError):
        delete_character("../../etc")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_characters.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'colouring_factory.characters'`

- [ ] **Step 3: Write the module**

Create `colouring_factory/characters.py`. It follows `storage.save_library_item` exactly: roots are functions rather than constants so a test's `monkeypatch.setenv` takes effect immediately, the directory is created as a side effect of asking for it, ids carry a timestamp so sorting is chronological, and the lister tolerates a half-written folder rather than dying.

```python
from __future__ import annotations

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .storage import data_root

# A person gets the rules about faces and hair; a toy gets told to keep its worn
# patches and its odd button. A character is anything else recognisable.
CHARACTER_KINDS = ("person", "toy", "character")


@dataclass(frozen=True)
class Character:
    id: str
    name: str
    kind: str
    marks: str
    created_at: str


def characters_root() -> Path:
    path = data_root() / "characters"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_character(
    *, photo: bytes, portrait: bytes, name: str, kind: str, marks: str
) -> str:
    name = name.strip()
    if not name:
        raise ValueError("A character needs a name.")
    if kind not in CHARACTER_KINDS:
        raise ValueError(f"Unknown kind of character: {kind}")
    if not photo or not portrait:
        raise ValueError("A character needs both a picture and a portrait.")

    # Microseconds, not seconds: three characters added in one minute still sort.
    character_id = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "-"
        + uuid.uuid4().hex[:8]
    )
    folder = characters_root() / character_id
    folder.mkdir(parents=True, exist_ok=False)

    (folder / "photo.png").write_bytes(photo)
    (folder / "portrait.png").write_bytes(portrait)
    (folder / "character.json").write_text(
        json.dumps(
            {
                "id": character_id,
                "name": name,
                "kind": kind,
                "marks": marks.strip(),
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return character_id


def _read(folder: Path) -> Character | None:
    try:
        payload: dict[str, Any] = json.loads(
            (folder / "character.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return None
    if not (folder / "portrait.png").exists():
        return None

    # Read through, the way quick_drawing_options does, so a hand-edited file
    # still yields something drawable rather than crashing the homepage.
    kind = str(payload.get("kind", "person"))
    return Character(
        id=str(payload.get("id", folder.name)),
        name=str(payload.get("name", "")).strip() or "Someone",
        kind=kind if kind in CHARACTER_KINDS else "person",
        marks=str(payload.get("marks", "")),
        created_at=str(payload.get("created_at", "")),
    )


def list_characters() -> list[Character]:
    found: list[Character] = []
    for folder in characters_root().iterdir():
        if not folder.is_dir():
            continue
        character = _read(folder)
        if character is not None:
            found.append(character)
    return sorted(found, key=lambda character: character.created_at, reverse=True)


def load_character(character_id: str) -> Character:
    character = _read(_folder_for(character_id))
    if character is None:
        raise FileNotFoundError(f"Character {character_id} was not found.")
    return character


def load_character_image(character_id: str, *, portrait: bool = True) -> bytes:
    chosen = _folder_for(character_id) / ("portrait.png" if portrait else "photo.png")
    if not chosen.exists():
        raise FileNotFoundError(f"Character {character_id} has no such picture.")
    return chosen.read_bytes()


def delete_character(character_id: str) -> None:
    folder = _folder_for(character_id)
    if folder.exists():
        shutil.rmtree(folder)


def _folder_for(character_id: str) -> Path:
    root = characters_root().resolve()
    folder = (characters_root() / character_id).resolve()
    if root not in folder.parents:
        raise ValueError("Invalid character path.")
    return folder
```

- [ ] **Step 4: Run them to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_characters.py -v`
Expected: 7 passed

- [ ] **Step 5: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`

```bash
git add colouring_factory/characters.py tests/test_characters.py
git commit -m "Keep a cast of characters on this computer"
```

---

### Task 6: The two prompt builders

Every rule below was arrived at by generation on 2026-08-30, not by taste. The face exemption is what makes a person recognisable without making the page fiddly; the hair rule is what survives the speck-removal pass; the empty-corners refusal is what stopped the model filling a badge's corners with scenery.

**Files:**
- Modify: `colouring_factory/prompts.py`
- Modify: `tests/test_prompts.py:40` (one assertion is deleted)
- Modify: `colouring_factory/guidance.py:70-81` (the `content` entry's `fix`)
- Create: `tests/test_character_prompts.py`

**Interfaces:**
- Consumes: `Character` from Task 5.
- Produces:
  - `build_character_scene_prompt(concept, characters, *, age_profile="2-3 years", style_name="Toddler bold", target="A4 page", extra_instructions="", variation_brief="") -> str` where `characters` is a sequence of `(name, kind, marks)` tuples in the same order the reference pictures are sent.
  - `build_caricature_prompt(name, kind, marks, *, age_profile="6-9 years") -> str`
  - `CHARACTER_LIKENESS_RULE`, `FACE_DETAIL_EXEMPTION`, `BADGE_CORNERS_RULE` as module constants so tests can assert on them by name.

Used by Tasks 7, 8 and 9.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_character_prompts.py`:

```python
import pytest

from colouring_factory.prompts import (
    BADGE_CORNERS_RULE,
    FACE_DETAIL_EXEMPTION,
    build_caricature_prompt,
    build_character_scene_prompt,
)


def test_each_character_is_named_and_matched_to_its_picture() -> None:
    prompt = build_character_scene_prompt(
        "building a sandcastle",
        [
            ("Ida", "person", "Curly hair, round glasses."),
            ("Bear", "toy", "A bald patch on one ear."),
        ],
    )

    assert "Ida" in prompt and "Bear" in prompt
    assert "Curly hair, round glasses." in prompt
    assert "A bald patch on one ear." in prompt
    # The order the pictures are attached in is the only thing telling the model
    # which face is which, so the prompt has to say so.
    assert "first" in prompt.lower() and "second" in prompt.lower()


def test_a_person_gets_the_face_exemption_and_a_toy_does_not() -> None:
    """A face at toddler detail comes back as a generic child.

    Proved on 2026-08-30: the same scene drawn with and without this exemption
    gave a stock cartoon face and a recognisable one. A toy needs no such rule,
    because a toy has no face for a model to smooth away.
    """

    with_person = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.")]
    )
    toy_only = build_character_scene_prompt(
        "having a picnic", [("Bear", "toy", "A bald patch on one ear.")]
    )

    assert FACE_DETAIL_EXEMPTION in with_person
    assert FACE_DETAIL_EXEMPTION not in toy_only


def test_hair_is_drawn_as_closed_shapes_not_strands() -> None:
    """Strands a pixel wide lose about a fifth of their ink to the despeckle
    pass and come back broken, so the rule is in the prompt rather than hoped
    for."""

    prompt = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.")]
    )
    assert "never as separate strands" in prompt


def test_the_colouring_book_contract_survives() -> None:
    prompt = build_character_scene_prompt(
        "walking in a forest", [("Ida", "person", "Curly hair.")]
    )
    assert "Pure white background." in prompt
    assert "Black line work only" in prompt


def test_a_caricature_refuses_the_corners_and_asks_for_exaggeration() -> None:
    prompt = build_caricature_prompt("Ida", "person", "Curly hair, round glasses.")

    assert BADGE_CORNERS_RULE in prompt
    assert "Draw NOTHING in the corners" in prompt
    # A polite, flattering portrait was the first attempt's failure, so the
    # prompt names it as the wrong answer.
    assert "wrong answer" in prompt


def test_a_scene_with_no_characters_is_refused() -> None:
    with pytest.raises(ValueError):
        build_character_scene_prompt("walking in a forest", [])
```

- [ ] **Step 2: Run them to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_character_prompts.py -v`
Expected: FAIL, `ImportError: cannot import name 'BADGE_CORNERS_RULE'`

- [ ] **Step 3: Add the three constants**

In `colouring_factory/prompts.py`, beneath `TARGET_RULES`:

```python
CHARACTER_LIKENESS_RULE = (
    "The attached pictures are the reference for how these characters really "
    "look. Draw each one as a friendly cartoon who is unmistakably recognisable "
    "as that particular character rather than a generic one. Draw hair as one or "
    "two large closed shapes that follow its real shape and length, never as "
    "separate strands. Show markings, worn patches and freckles as outlined "
    "shapes to colour, never as shading."
)

# A face is small on a page and carries all of the recognition, so it gets its
# own allowance while the rest of the sheet stays colourable. Without this, a
# face at the toddler level comes back as a stock cartoon child wearing the
# reference's glasses; with it, the same page keeps its big simple trees.
FACE_DETAIL_EXEMPTION = (
    "Detail exception, which overrides the reader profile for one part of the "
    "picture only: each person's head — the face, the hair and the glasses — may "
    "carry as much fine line work as it takes to be recognisably them, and should "
    "be drawn larger in the frame than realistic proportion would suggest. "
    "Everything else in the picture, including bodies, clothes and the whole "
    "setting, obeys the reader profile exactly: few, large, simple shapes with "
    "wide gaps."
)

# The polite version of this rule was ignored: told to leave the corners empty,
# the model filled them with a garden and added a decorative border. Refusing
# each thing by name is what worked.
BADGE_CORNERS_RULE = (
    "Composition rules for a round badge, which override everything else:\n"
    "- This picture will be cut into a circle. The four corners of the square are "
    "cut away and thrown out, so they must be left completely blank white.\n"
    "- Draw NOTHING in the corners: no background, no scenery, no border, no "
    "frame, no circle, no decorative edge of any kind.\n"
    "- The background behind the subject must be plain empty white. Do not invent "
    "a setting, a room, a garden, foliage or a pattern.\n"
    "- Place the whole head and shoulders inside an imaginary circle that touches "
    "the four edges of the square, centred, filling most of that circle."
)

ORDINALS = (
    "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth",
)
```

- [ ] **Step 4: Write `build_character_scene_prompt`**

It reuses the same visual contract as `build_colouring_prompt` rather than inventing a second one. Extract that block into a module constant `VISUAL_RULES` and have both builders use it, so the two cannot drift.

```python
def build_character_scene_prompt(
    concept: str,
    characters: Sequence[tuple[str, str, str]],
    *,
    age_profile: str = "2-3 years",
    style_name: str = "Toddler bold",
    target: str = "A4 page",
    extra_instructions: str = "",
    variation_brief: str = "",
) -> str:
    """A scene starring saved characters, drawn from their reference pictures.

    `characters` is (name, kind, marks) in the same order the reference pictures
    are attached, because that order is the only thing telling the model which
    face is which.
    """

    concept = concept.strip()
    if not concept:
        raise ValueError("A picture idea is required.")
    if not characters:
        raise ValueError("At least one character is required.")

    scene = variation_brief.strip() or concept
    style = STYLE_PRESETS.get(style_name, STYLE_PRESETS["Toddler bold"])
    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS[DEFAULT_LEVEL])
    target_rule = TARGET_RULES.get(target, TARGET_RULES["Flexible"])

    introductions = []
    for index, (name, kind, marks) in enumerate(characters):
        ordinal = ORDINALS[index] if index < len(ORDINALS) else f"number {index + 1}"
        article = "person" if kind == "person" else "character"
        line = f"The {ordinal} picture is {name}, a {article}."
        if marks.strip():
            line += f" {marks.strip()}"
        introductions.append(line)

    exemption = (
        f"\n{FACE_DETAIL_EXEMPTION}\n"
        if any(kind == "person" for _, kind, _ in characters)
        else ""
    )

    prompt = f"""
    Create an original black-and-white colouring-book illustration for {level.reader}.

    Scene: {scene}

    Who is in it:
    {chr(10).join(introductions)}

    {CHARACTER_LIKENESS_RULE}
    {exemption}
    {VISUAL_RULES}

    Style profile: {style.instruction}
    Reader profile: {level.regions}
    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    Composition profile: {target_rule}
    """

    if extra_instructions.strip():
        prompt += f"\nAdditional direction: {extra_instructions.strip()}\n"

    return dedent(prompt).strip()
```

- [ ] **Step 5: Write `build_caricature_prompt`**

```python
def build_caricature_prompt(
    name: str, kind: str, marks: str, *, age_profile: str = "6-9 years"
) -> str:
    """A head-and-shoulders caricature, composed for a round badge.

    The default level is 6-9 rather than the toddler default because a
    caricature is nothing but a face, so the detail belongs everywhere.
    """

    level = DETAIL_LEVELS.get(age_profile, DETAIL_LEVELS["6-9 years"])
    subject = "person" if kind == "person" else "character"
    marks_line = f" {marks.strip()}" if marks.strip() else ""

    prompt = f"""
    Create an original black-and-white colouring-book caricature.

    Subject: a good-natured caricature of {name}, the {subject} in the attached
    picture, head and shoulders only, facing forward.{marks_line}

    {CHARACTER_LIKENESS_RULE}

    Caricature direction: this is a seaside caricature, so exaggerate boldly and
    comically. Draw the head much larger than the body. Push the two or three
    most distinctive features far beyond life while keeping them unmistakably
    recognisable. Warm and affectionate, never unkind or ugly. A polite,
    accurate, flattering portrait is the wrong answer.

    {VISUAL_RULES}

    {BADGE_CORNERS_RULE}

    Line profile: {level.line_rule}
    Detail profile: {level.texture_rule}
    """

    return dedent(prompt).strip()
```

- [ ] **Step 6: Run them to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_character_prompts.py -v`
Expected: 6 passed

- [ ] **Step 7: Delete the imitation rule**

Remove this line from the visual rules in `colouring_factory/prompts.py`:

```
    - Do not imitate or reproduce an existing television, film, book or game character.
```

It contradicts the feature and, per the spec's judgement calls, a personal app drawing cartoons at home needs no such rule. Delete the single assertion that reads it, `tests/test_prompts.py:40`:

```python
    assert "existing television" in prompt
```

The surrounding test keeps its other four assertions and stays meaningful. Leave the word "original" in the opening line; it shapes the drawing rather than prohibiting a subject.

- [ ] **Step 8: Reword the content guidance**

In `colouring_factory/guidance.py`, the `fix` text currently reads as a Doodle house rule the app no longer has. Change only that field:

```python
        fix=(
            "The provider's own filter rejected that wording. Describing the "
            "picture in your own words usually gets through."
        ),
```

- [ ] **Step 9: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`
Expected: all green, with one fewer assertion in `test_prompts.py`.

```bash
git add colouring_factory/prompts.py colouring_factory/guidance.py tests/test_prompts.py tests/test_character_prompts.py
git commit -m "Ask for a particular character, and stop refusing to draw cartoons"
```

---

### Task 7: The characters screen

This is the first task with something to use, and it is also the whole cartoon feature: adding a character draws their caricature, and that caricature becomes the current doodle through `_adopt_artwork`, inheriting the A4 page, the badge strip, printing, saving and *Colour it in for me*.

**Files:**
- Modify: `app.py` — `_initialise_state`, the router block at 1807-1821, `_start_new_doodle`
- Create: `tests/test_app_characters.py`

**Interfaces:**
- Consumes: Tasks 3, 4, 5, 6.
- Produces:
  - Session keys `characters_return: str = "home"`, `character_draft: dict`, `chosen_characters: list[str]`.
  - `screen == "characters"` renders `_render_characters_screen()`.
  - `_draw_character_portrait(photo: bytes, name: str, kind: str, marks: str) -> GeneratedArtwork`.

- [ ] **Step 1: Write the failing test that the screen exists at all**

The router has five `if screen == ...: render; st.stop()` branches and no `else`, so an unknown screen silently renders the whole Studio with no error. Assert the screen is real rather than assuming a new value routes:

Create `tests/test_app_characters.py`:

```python
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP = str(PROJECT_ROOT / "app.py")
ARTWORK = (PROJECT_ROOT / "assets" / "demo_dinosaur.png").read_bytes()


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("DOODLE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("COLOURING_FACTORY_DATA_DIR", raising=False)
    for variable in ("GEMINI_API_KEY", "RECRAFT_API_TOKEN"):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")


def _characters_screen() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["screen"] = "characters"
    at.run()
    return at


def test_the_characters_screen_is_its_own_screen() -> None:
    """The router falls through to Studio for any unknown value.

    Without its own branch a characters screen renders the full Studio and
    nobody notices, so assert on something only this screen shows.
    """

    at = _characters_screen()
    assert not at.exception
    headings = [element.value for element in at.get("heading")]
    assert any("character" in str(heading).lower() for heading in headings)
    # The Studio's own controls must not be on this screen.
    assert not [radio for radio in at.radio if radio.label == "Artwork source"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_app_characters.py -v`
Expected: FAIL, the Studio's "Artwork source" radio is present.

- [ ] **Step 3: Add the state, the route and the branch**

In `_initialise_state`, add to `defaults`:

```python
        "characters_return": "home",
        "character_draft": {},
        # The picker's ticks live here rather than in per-name widget keys.
        # Streamlit garbage-collects a widget key the moment its widget is not
        # rendered, so ticking someone, visiting this screen and coming back
        # would silently lose every tick.
        "chosen_characters": [],
```

In `_start_new_doodle`, clear `character_draft` but **not** `chosen_characters`: a parent drawing for the same children wants the same cast next time, which is the same reasoning the homepage settings already follow.

Add the branch to the router block, before the `library` branch:

```python
if st.session_state.screen == "characters":
    _render_characters_screen()
    st.stop()
```

- [ ] **Step 4: Write the failing test for adding a character**

```python
def test_adding_a_character_draws_a_portrait_and_saves_it(monkeypatch) -> None:
    import app as doodle_app

    def fake_refine(**kwargs):
        assert kwargs["reference_images"]
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    monkeypatch.setattr(doodle_app, "refine_with_provider", fake_refine)

    at = _characters_screen()
    at.get("file_uploader")[0].set_value(("ida.png", PHOTO_BYTES, "image/png"))
    at.text_input(key="character_name").set_value("Ida").run()
    at.text_area(key="character_marks").set_value("Curly hair, round glasses.").run()

    for button in at.button:
        if button.label == "Draw them":
            button.click().run()
            break
    else:
        raise AssertionError("Draw them button not found")

    assert not at.exception
    assert [c.name for c in list_characters()] == ["Ida"]
    # The portrait is a doodle like any other, so it lands on the result screen.
    assert at.session_state["screen"] == "result"
    assert at.session_state["quick_processed"]
```

- [ ] **Step 5: Run it to verify it fails, then build the screen**

`_render_characters_screen()` renders, in this order: the shared top bar via `_render_top_bar(where="characters")`; the existing cast as a grid of portraits with a delete button each, confirmed the way `_render_library_grid` confirms a delete; then the add form.

The add form holds an `st.file_uploader` (label `"Add a picture"`, `type=["png", "jpg", "jpeg", "webp", "heic"]`), a `st.text_input` keyed `character_name`, an `st.segmented_control` for the kind (`"A person"`, `"A toy"`, `"Something else"` mapped to `CHARACTER_KINDS`), a `st.text_area` keyed `character_marks` with a caption prompting for what to write, and one primary button `"Draw them"`.

On click:

```python
    photo = prepare_photo(uploaded.getvalue())
    artwork = _draw_character_portrait(photo, name, kind, marks)
    save_character(
        photo=photo,
        portrait=artwork.image_bytes,
        name=name,
        kind=kind,
        marks=marks,
    )
    _adopt_artwork(artwork, f"{name}, drawn by Doodle")
    _prepare_quick_outputs()
    st.session_state.screen = "result"
    st.rerun()
```

and `_draw_character_portrait` is the wiring, reusing the model-resolution three-liner that already appears three times in `app.py` — extract it to `_model_for(provider_id, spec, settings)` and use it in all four places rather than writing a fourth copy:

```python
def _draw_character_portrait(photo, name, kind, marks):
    provider_id = _active_provider_id()
    spec = get_provider(provider_id)
    api_key, _source = _provider_key(provider_id)
    return refine_with_provider(
        provider_id=provider_id,
        api_key=api_key,
        prompt=build_caricature_prompt(name, kind, marks),
        reference_images=(photo,),
        model=_model_for(provider_id, spec, load_settings()),
        size=spec.square_size,
        quality=str(load_settings().get("openai_quality", DEFAULT_QUALITY)),
    )
```

Note `spec.square_size`, not `portrait_size`: a caricature is a face, and a face is the most badge-shaped thing Doodle draws.

- [ ] **Step 6: Write the failing test for a declined photograph**

```python
def test_a_declined_photograph_is_explained_as_a_picture_problem(monkeypatch) -> None:
    import app as doodle_app

    def refuse(**kwargs):
        raise GeneratorError(
            "OpenAI would not draw from that picture.",
            provider="OpenAI",
            code="photo_declined",
        )

    monkeypatch.setattr(doodle_app, "refine_with_provider", refuse)
    at = _characters_screen()
    ...  # fill the form and click as above

    errors = " ".join(str(error.value) for error in at.error)
    assert "picture" in errors.lower()
    # The old content guidance blamed the wording and pointed at the idea box.
    assert "television" not in errors.lower()
    assert list_characters() == []
```

- [ ] **Step 7: Handle the failure**

Wrap the click handler so a `GeneratorError` renders through `_show_guidance(error.code, detail=str(error))` and nothing is saved. A character with no portrait must never reach the store.

- [ ] **Step 8: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`

```bash
git add app.py tests/test_app_characters.py
git commit -m "Add a character, and get their cartoon as a doodle"
```

---

### Task 8: The characters picker on the homepage

**Files:**
- Modify: `app.py` — `_render_home_options`, `_quick_generate`
- Modify: `tests/test_app_characters.py`

**Interfaces:**
- Consumes: Tasks 5, 6, 7.
- Produces: `_quick_generate` sends `reference_images` and uses `build_character_scene_prompt` whenever `chosen_characters` is non-empty.

- [ ] **Step 1: Write the failing test that the ticks survive a trip away**

```python
def test_a_ticked_character_survives_going_to_the_add_screen_and_back() -> None:
    """Per-name widget keys are destroyed the moment they are not rendered.

    Proved on 2026-08-30: tick a character, navigate away, come back, and the
    key reads False. setdefault does not help, because the key is deleted
    after the run in which the widget is absent.
    """

    _save_two_characters()
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()

    at.checkbox(key="character_pick_Ida").set_value(True).run()
    at.session_state["screen"] = "characters"
    at.run()
    at.session_state["screen"] = "home"
    at.run()

    assert at.session_state["chosen_characters"] == ["Ida"]
    assert at.checkbox(key="character_pick_Ida").value is True
```

- [ ] **Step 2: Run it to verify it fails, then build the popover**

In `_render_home_options`, add a fourth `st.popover` to the same horizontal container. The label is a **count**, never a joined list of names: the settings line uses `flex: 0 0 auto` with `white-space: nowrap` and `text-overflow: clip` inside a `.block-container` carrying `overflow: visible !important`, so one long label pushes the whole page sideways on a phone.

```python
    chosen = list(st.session_state.get("chosen_characters", []))
    cast = list_characters()
    if cast:
        count = len([name for name in chosen if name in {c.name for c in cast}])
        label = "nobody" if not count else f"{count} character{'' if count == 1 else 's'}"
        with st.popover(label):
            st.caption("Doodle draws these characters into the picture.")
            for character in cast:
                st.checkbox(
                    character.name,
                    key=f"character_pick_{character.name}",
                    value=character.name in chosen,
                    on_change=_remember_chosen,
                    args=(character.name,),
                )
            if st.button("Add someone", width="stretch"):
                st.session_state.characters_return = "home"
                st.session_state.screen = "characters"
                st.rerun()
```

with the selection kept in the plain key:

```python
def _remember_chosen(name: str) -> None:
    """Widget keys vanish when their widget is not rendered, so the answer
    lives in a plain key and each box is told its value on the way in."""

    chosen = list(st.session_state.get("chosen_characters", []))
    if st.session_state.get(f"character_pick_{name}"):
        if name not in chosen:
            chosen.append(name)
    elif name in chosen:
        chosen.remove(name)
    st.session_state.chosen_characters = chosen
```

The popover renders only when there is at least one character, following the rule the homepage already applies to `Saved doodles (n)`.

- [ ] **Step 3: Write the failing test that a chosen character reaches the drawing**

```python
def test_a_chosen_character_is_sent_as_a_reference(monkeypatch) -> None:
    captured = {}

    def fake_refine(**kwargs):
        captured.update(kwargs)
        return GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )

    import app as doodle_app
    monkeypatch.setattr(doodle_app, "refine_with_provider", fake_refine)
    _save_two_characters()

    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["chosen_characters"] = ["Ida"]
    at.session_state["screen"] = "generate"
    at.session_state["generation_idea"] = "walking in a forest"
    at.run()

    assert len(captured["reference_images"]) == 1
    assert "Ida" in captured["prompt"]
    assert "never as separate strands" in captured["prompt"]
```

- [ ] **Step 4: Branch `_quick_generate`**

Where the AI branch builds `prompts` and calls `generate_with_provider`, add a preceding branch. A character drawing goes through `refine_with_provider` because that is the call that carries pictures; alternatives still work, one call per brief.

```python
        chosen = _cast_for_drawing()  # [(id, name, kind, marks)] filtered to what exists
        if chosen:
            references = tuple(
                load_character_image(character_id) for character_id, *_ in chosen
            )
            artworks = [
                refine_with_provider(
                    provider_id=provider_id,
                    api_key=api_key,
                    prompt=build_character_scene_prompt(
                        idea,
                        [(name, kind, marks) for _, name, kind, marks in chosen],
                        age_profile=str(options["age_profile"]),
                        style_name=str(options["style"]),
                        target="A4 page",
                        variation_brief=brief,
                    ),
                    reference_images=references,
                    model=model,
                    size=spec.portrait_size,
                    quality=quality,
                )
                for brief in briefs
            ]
```

`_cast_for_drawing` reads `chosen_characters`, resolves each name against `list_characters()` and drops any that no longer exist, so a deleted character cannot break the homepage. That is the same read-through discipline `quick_drawing_options` uses.

The references are the **portraits**, not the photographs: the spike showed the likeness survives the second hop, and using the portrait means the same drawn character appears in every picture rather than a slightly different one each time.

- [ ] **Step 5: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`

```bash
git add app.py tests/test_app_characters.py
git commit -m "Put your characters in the picture from the homepage"
```

---

### Task 9: The badge strip

**Files:**
- Modify: `app.py` — `_quick_generate`, `_render_first_result`, `_start_new_doodle`, `_initialise_state`
- Create: `tests/test_app_badge_strip.py`

**Interfaces:**
- Consumes: Task 2's guarantee that the version chain matches the picture on screen.
- Produces: session keys `badge_preview: bytes | None`, `badge_raw: bytes | None`; `_prepare_badge_outputs()`; `_render_badge_strip()`.

- [ ] **Step 1: Write the failing test**

```python
def test_the_result_screen_shows_the_doodle_as_a_badge() -> None:
    at = _result_screen()
    captions = " ".join(str(caption.value) for caption in at.caption)
    assert "badge" in captions.lower()
    assert at.session_state["badge_preview"]


def test_drawing_it_for_a_badge_asks_for_a_square_composed_picture(monkeypatch) -> None:
    captured = {}

    def fake_generate(**kwargs):
        captured.update(kwargs)
        return [GeneratedArtwork(
            image_bytes=ARTWORK, prompt="p", provider="OpenAI", model="gpt-image-2"
        )]

    import app as doodle_app
    monkeypatch.setattr(doodle_app, "generate_with_provider", fake_generate)

    at = _result_screen()
    for button in at.button:
        if button.label == "Draw it for a badge":
            button.click().run()
            break
    else:
        raise AssertionError("Draw it for a badge button not found")

    assert not at.exception
    # A picture composed for a page puts a small figure in a landscape the
    # circle then cuts away, so the redraw asks for square and for corners.
    assert captured["size"] == "1024x1024"
    assert "cut into a circle" in captured["prompts"][0]
```

- [ ] **Step 2: Run to verify failure, then prepare the preview eagerly**

Follow the pattern `_prepare_pair_outputs` established: prepare inside `_quick_generate`, park bytes in plain session keys, render with a self-guarding function. Add after `_prepare_pair_outputs()`:

```python
def _prepare_badge_outputs() -> None:
    """Fit the finished picture into a 58 mm badge, which costs nothing.

    A separate function from the redraw: this one only re-lays-out what is
    already drawn, so it is instant and free and can be shown without asking.
    """

    processed = st.session_state.get("quick_processed")
    if not processed:
        st.session_state.badge_preview = None
        return

    # The calibration profile is read only after the result screen's st.stop(),
    # so this cannot borrow it and loads its own.
    calibration = CalibrationProfile.from_dict(load_settings().get("calibration"))
    st.session_state.badge_preview = _cached_badge_preview(
        processed, BADGE_58MM, calibration
    )
```

with `BADGE_58MM = CircleSheetConfig(finished_diameter_mm=58.0, cut_diameter_mm=58.0, safe_diameter_mm=50.0)` as a module constant beside `A4_SHEET`.

- [ ] **Step 3: Render the strip**

Called from `_render_first_result` immediately after `_render_grown_up_sheet()`, inside `st.container(border=True)`, showing the preview, a caption naming the size, and the redraw button with its cost named the way the colour button already does:

```python
        st.caption(
            "Your doodle fitted to a 58 mm badge. Doodle can draw it again "
            "composed for the circle instead, which costs one drawing."
        )
```

- [ ] **Step 4: Wire the redraw**

The redraw goes through the same path a homepage drawing takes, with `target="Round badge"` and `spec.square_size`, and it adopts its result so the new picture becomes the doodle with its own badge strip. When characters are chosen it uses `build_character_scene_prompt(..., target="Round badge")` and their portraits; otherwise `build_colouring_prompt(..., target="Round badge")`.

- [ ] **Step 5: Clear the keys on a new doodle**

Add `badge_preview` and `badge_raw` to `_start_new_doodle` and to `_initialise_state`'s defaults, since they are not content-hashed the way `colour_previews` is.

- [ ] **Step 6: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`

```bash
git add app.py tests/test_app_badge_strip.py
git commit -m "Show every doodle as a badge, and offer to draw one properly"
```

---

### Task 10: Say what the app now does

**Files:**
- Modify: `app.py` (the privacy paragraph in the guide tab)
- Modify: `README.md`
- Modify: `docs/ui-conventions.md`

- [ ] **Step 1: Replace the privacy paragraph**

The current text claims uploaded pictures stay in the local folder, which this feature makes false. Replace it with:

```python
        st.markdown(
            "**Privacy and files**\n\n"
            "Doodle sends the written idea to the drawing service you have "
            "connected, and when a picture has your characters in it, it sends "
            "their portraits too. Everything else stays on this computer: your "
            "characters live in the local data folder along with the photographs "
            "you added them from, and so do your saved doodles.\n\n"
            "Removing someone from your characters deletes their photograph from "
            "this computer, which is the only copy Doodle has; it cannot recall "
            "anything a drawing service has already been sent. What each service "
            "does with what it receives is set out in its own terms, not here."
        )
```

- [ ] **Step 2: Add a conventions section**

In `docs/ui-conventions.md`, following the style of the existing "One idea, two readers" section, record three decisions so a later change has to argue with them: that the homepage settings line carries counts rather than name lists and why; that a person is always drawn at full facial fidelity with no setting to turn it down; and that every picture Doodle makes reaches the badge machinery through the ordinary artwork lifecycle rather than a private path.

- [ ] **Step 3: Update the README feature list**

Add saved characters, drawing them into a scene, the caricature, and the badge strip. Note `pillow-heif` in the dependency list with one line on why.

- [ ] **Step 4: Run the full suite and commit**

Run: `.venv/bin/python -m pytest`

```bash
git add app.py README.md docs/ui-conventions.md
git commit -m "Say what leaves this computer, now that pictures of people do"
```

---

## Self-review notes

- Every section of the spec maps to a task: the store to 5, photograph handling to 3, the drawing primitive to 4, the prompts and the deleted imitation rule to 6, the homepage to 8, the cartoon route to 7, the badge strip to 9, the refusal path to 4 and 7, the privacy wording to 10, and all five listed blockers to 1, 2 and 7.
- Names are consistent across tasks: `prepare_photo`, `save_character`, `list_characters`, `load_character_image`, `build_character_scene_prompt`, `build_caricature_prompt`, `max_reference_images`, `reference_images`, `chosen_characters`, `badge_preview`.
- Two things remain assumptions and are marked as such in the spec rather than planned around: whether a provider accepts a photograph of a real child, and whether Gemini draws from several references in practice. Neither blocks any task.
