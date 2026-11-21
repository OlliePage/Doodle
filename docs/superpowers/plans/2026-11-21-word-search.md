# Word search: implementation plan

Spec: `docs/superpowers/specs/2026-11-21-word-search-design.md`.

How this plan runs:

- Tasks 1–4 are independent modules, each in its own file, and run in parallel.
- Task 5 wires them into `app.py` once they are merged on the branch.
- Every task has pure-function tests in `tests/`. Anything a parent sees is
  tested through Streamlit's `AppTest`, which clicks the controls rather than
  only checking they exist.

## Task 1: the puzzle engine (`colouring_factory/wordsearch.py`)

- [ ] `WordSearchSettings`, a frozen dataclass with these fields:
  - `rows`, `cols`
  - `word_count`
  - `min_len`, `max_len`
  - `directions`, a frozenset of `"across"`, `"down"`, `"diagonal"` and `"backwards"`
  - `uppercase: bool`
  - `to_dict` and `from_dict` (for saving favourites)
- [ ] `PRESETS: dict[str, WordSearchSettings]` keyed by the four strings in
  `storage.QUICK_AGE_CHOICES`, with the values from the spec's table.
- [ ] `parse_word_input(text) -> WordInput`. Returns kind `"words"` (with a
  list of `(display, letters)` pairs) when the text has a comma or new line,
  and kind `"topic"` otherwise. Letters keep A–Z only and are upper-cased.
  Blank entries and duplicates are dropped.
- [ ] `build_puzzle(words, settings, seed) -> Puzzle`.
  - `Puzzle` holds the grid (a tuple of row strings), the placements (word,
    start row and column, direction step), the words placed and the words
    skipped, each skipped word with a reason.
  - Directions are mapped to steps. Across is (0,1), down is (1,0) and diagonal
    is (1,1) and (-1,1). Backwards adds the reverse of every allowed step.
  - Longest words are placed first, with randomised attempts and overlaps
    allowed where the letters match.
  - A word that will not fit is skipped with a reason rather than raising.
  - Empty cells are filled with random letters. Ages 2-3 and 4-5 fill only from
    letters that do not spell the target words' first letters next to each
    other. Keep this simple: random A–Z is acceptable if that check is too
    complicated.
  - Lower-case is applied at the end when `uppercase` is false.
- [ ] Tests (`tests/test_wordsearch.py`):
  - each placement reads back from the grid;
  - only allowed directions are used;
  - the same seed gives the same grid;
  - a word too long for the grid is skipped with a reason;
  - the parse rules (commas, new lines, a phrase with spaces, dropping punctuation).

## Task 2: words for a topic (`colouring_factory/wordsearch_words.py`)

- [ ] `BUILT_IN_TOPICS: dict[str, tuple[str, ...]]`, about 12 topics with at
  least 20 short concrete nouns each. Matching tolerates plurals and a few
  synonyms ("kitchen things" finds kitchen, "family" finds family members,
  "sea creatures" finds sea).
- [ ] `words_for_topic(topic, settings, *, provider_id, api_key) -> list[str]`.
  It returns display words.
  - When the provider has a text model, ask it through the same helpers as
    `colouring_factory/variations.py` (`_openai_text`, `_google_text`,
    `_extract_json_array`). Reuse them; do not copy them.
  - Ask for `word_count + 4` candidates and keep those within the length limits.
  - Fall back to the built-in list when there is no text model or the call
    raises.
  - Raise `GeneratorError(code="unknown_topic")` when neither source has words.
  - Add that code to `colouring_factory/guidance.py`, because
    `tests/test_guidance.py` requires every error code to have guidance.
- [ ] Tests:
  - the built-in fallback, and synonyms matching;
  - a faked text model's reply being filtered by length;
  - a text-model failure falling back to the built-in list;
  - an unknown topic with no text model raising.

## Task 3: picture clues (`colouring_factory/wordsearch_clues.py`)

- [ ] `clue_prompt(word) -> str`. It asks for a single object, centred, with
  thick clean black outlines on white, no background, no text and no shading,
  colourable by a young child.
- [ ] `clue_picture(word, *, provider_id, model, api_key) -> bytes`.
  - Draw it with `generators.generate_with_provider`, using the provider's
    square size and the lowest quality.
  - Clean it with `image_processing.normalise_line_art`.
  - Cache the result under `data_root()/clue_cache/<provider>/<model>/<word>.png`.
  - Return the cached bytes when they exist.
- [ ] `clue_pictures(words, ...) -> dict[str, bytes | None]`. It draws the
  missing clues, at most four at once, using a thread pool. A clue that fails
  maps to `None`, so the sheet is still made.
- [ ] Tests (with `generate_with_provider` faked):
  - the cache is hit on the second call with no new request;
  - one failure gives `None` without stopping the others;
  - the prompt contains the word.

## Task 4: the PDF and preview (`colouring_factory/wordsearch_pdf.py`)

- [ ] `create_wordsearch_pdf(puzzle, *, title, clues, show_pictures) -> bytes`.
  It uses reportlab and two A4 pages.
  - **Page 1:** the title, then the grid in square cells sized to the page
    width and drawn in Helvetica-Bold, then the clue list. Each clue is a
    picture box with the display word under it. Pictures are omitted when
    `show_pictures` is false or a clue is `None`.
  - **Page 2:** "Answers", with the same grid and a rounded outline around
    each placed word, drawn along its direction.
  - The letter size never goes below 24 pt when the grid is 6 × 6 or smaller.
- [ ] `preview_png(pdf_bytes, page=0, zoom=1.5) -> bytes`, rendered with PyMuPDF
  (`fitz`).
- [ ] Tests:
  - the PDF has two pages (checked with pypdf);
  - page 1's text contains every placed word and its title;
  - the preview is a valid PNG;
  - a puzzle with no clues still renders.

## Task 5: wiring it into the app (`app.py`)

- [ ] A homepage switch, `st.segmented_control` with key `home_mode`, offering
  `Colouring page` and `Word search`. The choice is saved in settings as
  `home_mode`.
- [ ] In word search mode:
  - the placeholder changes as the spec says;
  - the settings line shows the difficulty popover and the image-model item,
    and hides the pictures, style and characters items;
  - the button label is `Make the word search`.
- [ ] The difficulty popover offers:
  - the four presets;
  - the saved favourites (from `settings["wordsearch_favourites"]`, a list of
    `{name, settings}`), with delete;
  - a Custom section with the controls from the spec, `Save as a favourite`
    and a name box;
  - the `Pictures beside the words` toggle.
- [ ] Making a sheet:
  - parse the input, then get the words, the puzzle, the clues (when pictures
    are on, with a spinner naming the model) and the PDF and preview;
  - errors go through the same guidance routing as drawing.
- [ ] The result screen for a word search shows:
  - the preview, `Print this word search` (primary) and `Save as a PDF`;
  - `Make another`, which uses the same words, a new seed and the cached
    pictures;
  - `Add to favourites`, and the Back and Forward arrows.
- [ ] History: record the sheet with metadata `kind: "wordsearch"`, the words,
  the settings and the seed. The preview PNG is stored as its image, and the
  PDF is rebuilt on reopen from the cached clues. Reopening lands on the word
  search result.
- [ ] AppTest coverage, clicking every control:
  - switching mode;
  - typed words producing a result;
  - a topic with the text model faked;
  - saving and choosing a favourite difficulty;
  - Make another;
  - reopening from History.
- [ ] Update `docs/ui-conventions.md` with the new labels.

## Finish

- [ ] Run the full suite and `ruff`.
- [ ] Check the homepage and result screen in a browser.
- [ ] Mark the PR ready and merge it.
