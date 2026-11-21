# Word searches

Ollie's younger daughter is four and ready for word searches. Doodle should make
printable ones, from a topic ("animals", "kitchen things", "our family") or
from words he types, pitched at her age, with a picture beside every word
because she cannot read the list yet.

Decisions taken with Ollie on 2026-11-21:

- Each word in the list has a small colourable line drawing beside it.
- Difficulty comes from the age presets already on the homepage, and there
  is also a custom setting. A custom setting can be saved as a favourite so
  it is one tap next time.
- Word searches live behind a switch on the homepage, not on a separate screen.

## What the parent sees

**Homepage.** A switch above the idea box: `Colouring page` / `Word search`.
In word search mode:

- The placeholder becomes "A topic, or your own words: cat, dog, hen".
- The settings line swaps the picture-count and style items for one
  difficulty item, labelled with the preset name (for example `4-5 years`)
  or the favourite's name.
- The button says `Make the word search`.

**Input rules.** If the text contains a comma or a new line, it is a list of
the parent's own words, used as typed. Otherwise it is a topic. Words are
reduced to letters only and upper-cased. Spaces in a typed phrase are removed,
so "fire engine" becomes FIREENGINE, and the clue under its picture still
reads "fire engine". A word longer than the grid allows is reported by name
and left out; the rest of the sheet still gets made.

**Topic words.** The connected provider's text model is asked for N concrete,
picturable, child-familiar nouns on the topic, each within the preset's length
limits. If there is no text model (Recraft) or the call fails, Doodle uses a
built-in list for about a dozen common topics: animals, farm, kitchen, family,
toys, food, fruit, vegetables, sea, transport, clothes, garden and weather. A
topic matching none of these, with no text model, is reported plainly.

**Difficulty.**

| Preset    | Grid    | Words | Word length | Directions                                  |
|-----------|---------|-------|-------------|---------------------------------------------|
| 2-3 years | 5 × 5   | 3     | 3–4         | across                                      |
| 4-5 years | 6 × 6   | 5     | 3–5         | across, down                                |
| 6-9 years | 10 × 10 | 8     | 3–8         | across, down, diagonal                      |
| Grown-up  | 14 × 14 | 14    | 4–12        | all eight directions, including backwards   |

Custom offers four settings:

- grid size, from 5 to 15;
- number of words, from 3 to 15;
- which directions are allowed (across, down, diagonal, backwards);
- capitals or lower-case letters.

Below them is `Save as a favourite` with a name box. Saved favourites appear in
the difficulty panel as one-tap choices and can be deleted.

**Picture clues.** One small line drawing per word is drawn by the active image
model, using the provider's cheapest quality setting. The prompt asks for a
single object, centred, with bold outlines and no background, so it prints
as a colourable icon. Pictures are cached on disk by word and model, so CAT is
paid for once. A sheet can be made with `Pictures beside the words` switched
off, which is instant and free.

**Result screen.** The result screen shows a preview of the sheet. It also has:

- `Print this word search` (the primary button) and `Save as a PDF`;
- `Make another`, which uses the same words in a fresh grid and costs nothing,
  because the pictures are cached;
- `Add to favourites`.

The sheet is recorded in History like any doodle, and reopening it from
History brings the same sheet back.

**The PDF.** The PDF has two A4 pages.

- **Page 1:** a title (the topic, or "Find these words"), the letter grid in
  large letters sized to fill the width, and below it the clue list. Each
  clue is a picture with the word printed under it, laid out in a row or two.
- **Page 2:** the answer key, which is the same grid with each word ringed.

Letters use a clear sans-serif font. The 2-3 and 4-5 presets use at least
24 pt.

## Out of scope

Crosswords and other puzzles, a word bank shared between sheets, and editing
the grid by hand.

## Where the code goes

| Module | Holds |
|---|---|
| `colouring_factory/wordsearch.py` | Settings, presets, input parsing and the grid builder. Pure functions, seeded so tests are deterministic. |
| `colouring_factory/wordsearch_words.py` | The topic-to-words step through the text model, and the built-in lists. |
| `colouring_factory/wordsearch_clues.py` | The picture prompt, generating a clue and caching it on disk. |
| `colouring_factory/wordsearch_pdf.py` | The two-page PDF, and a PNG preview of page 1 rendered with PyMuPDF. |
| `app.py` | The homepage switch, the difficulty panel, the making flow, the result screen and History. |
