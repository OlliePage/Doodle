# Drop a picture — implementation plan

**Goal:** Drag a picture anywhere onto Doodle, see it appear in the prompt bar, and have the homepage settings draw with it.

**Architecture:** Injected JavaScript catches the drag on `window` and forwards the file into a hidden `st.file_uploader`, so the bytes travel over Streamlit's own upload endpoint rather than the websocket. A dropped picture is treated as a character you never saved: it supplies identity, the typed words supply the scene.

**Tech Stack:** Streamlit 1.62.0, Pillow, pytest + `streamlit.testing.v1.AppTest`.

**Spec:** `docs/superpowers/specs/2026-08-31-drop-a-picture-design.md`

## Global constraints

- The `st.html` payload must be byte-identical on every rerun. No nonce, no session state, nothing per-screen or per-provider inside it.
- Nothing user-supplied may reach the injected template. It is rendered with `unsafe_allow_javascript=True`.
- Sentence case everywhere. Material Symbols only, never emoji. Verb-phrase button labels.
- One primary button per screen.
- The homepage keeps its shape: one full-width element, the button that acts on it, and a line of settings. Nothing new below the bar.
- Every byte goes through `prepare_photo`.
- Never assign to a widget key from the script body; bump a nonce in the key instead.
- Patch provider functions on `colouring_factory.*`, never on `app`.
- Click every button in tests; asserting presence proves nothing.

---

- [x] **Task 1 — `colouring_factory/browser_drop.py`**: pure function returning the overlay's HTML, CSS and JavaScript, plus `DROP_EXTENSIONS` and `DROP_MAX_BYTES`. Unit tests in `tests/test_browser_drop.py`: guard present, extensions and ceiling interpolated, byte-identical across calls, refuses a non-alphanumeric extension, no placeholder left.
- [x] **Task 2 — `colouring_factory/prompts.py`**: `DROPPED_PICTURE_RULE`; `build_character_scene_prompt` gains `dropped_appearance: str | None`; the dropped picture is always introduced last; `PORTRAIT_MATCH_RULE` only when there is a cast; the face exemption fires for a dropped picture too; `CAST_FOREGROUND_RULE` reworded to cover both. Tests in `tests/test_character_prompts.py`.
- [x] **Task 3 — the drop well and adoption**: overlay rendered once at module level; `_render_drop_well()` inside `st.container(key="doodle-drop-well")`, outside the form, hidden by homepage CSS; `_adopt_dropped_picture()` running `prepare_photo`, the sha256 dedupe, `describe_appearance` failing soft, and `quick_mode = "ai"`. New session keys declared and cleared.
- [x] **Task 4 — the prompt bar**: thumbnail inside the pill, `Remove picture` as a second form submit button, placeholder change.
- [x] **Task 5 — drawing with it**: `_submit_home_prompt` proceeds on a blank prompt when a picture is attached; `_build_generation_plan` attaches the picture last and picks the scene builder; `generation_uses_cast` → `generation_uses_references` across all six sites.
- [x] **Task 6 — slots and Recraft**: cast cap reduced by one while a picture is attached; Recraft refused at adoption with `no_reference_support`.
- [x] **Task 7 — the other two screens**: characters and Studio uploaders wrapped in the same keyed container so a whole-page drop fills them.
- [x] **Task 8 — privacy copy**: the About paragraph gains a sentence about dropped pictures, and the stale portrait-versus-photograph claim is corrected in all three places.
- [x] **Task 9 — verification**: full pytest suite, ruff, and the Chrome DevTools proof re-run against the real app.
