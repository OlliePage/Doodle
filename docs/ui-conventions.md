# Doodle interface conventions

Written 2026-08-30 after a consistency pass over every screen. These are the
rules the interface follows; a change that breaks one should change this file
too, or be reconsidered.

## Naming

**Doodle is the app. A doodle is a picture.** Capital D only when it names the
application or the Studio. "Save this doodle", "Open Doodle Studio", "Saved
doodles".

**One label per concept, across every form.** The three layout forms each set a
caption, a caption size and a margin, and each had invented its own wording for
them. The same setting reads the same wherever it appears:

| Concept | Label |
|---|---|
| Caption text | `Caption (optional)` |
| Caption size | `Caption size (pt)` |
| Margin around the artwork | `Margin (mm)` |
| Margin around a badge grid | `Outer margin (mm)` |

The last is deliberately different: it is the margin around the whole sheet of
badges, not around one picture, so sharing a name would mislead.

**One label per action.** Returning to a blank homepage is `New doodle`
everywhere. Drawing is `Draw`, never `Create` or `Generate`.

## Casing

Sentence case for every label, button, heading and tab. Not Title Case. Proper
nouns keep their capitals: `Open OpenAI API keys`, `Doodle Studio`.

## Icons

Material Symbols (`icon=":material/name:"`), never emoji or typed glyphs. Arrows
such as `←` and `↗`, and symbols such as `♡` and `↻`, were used as makeshift
icons on four buttons; they render at text weight, do not match the Material set
used elsewhere, and are read aloud as punctuation by a screen reader.

The page icon in `st.set_page_config` stays an emoji, because that parameter
takes no Material Symbol.

## Buttons

One primary button per screen, on the action that screen exists for. Everything
else is secondary. A button label is a verb phrase describing what happens:
`Draw it`, `Build the PDF`, `Save to your doodles`.

Step numbers belong in the step heading above a control, never inside the
button's own label.

## Instructions

Help that explains a control goes in `help=` or a caption beneath it, not inside
the label. `Copies (0 = fill sheet)` put a rule where the name should be.

## Native elements over HTML

Prefer Streamlit's own elements. `st.container(border=True)` for grouping,
`st.segmented_control` for a compact either/or. Injected CSS is limited to the
homepage, where the defect being fixed lives inside Streamlit's own input chrome
and no native API reaches it.

## Routes

Saved doodles are reachable from wherever a doodle exists, never only from
inside Doodle Studio. Saving used to end at a disabled `Saved` button with no
route onward, so the library it wrote to was effectively invisible. The rules:

- The result screen's save button becomes the route to what it just saved.
- The homepage offers `Saved doodles (n)` in the top-right corner once there is
  at least one, out of the centre column, and shows nothing there before that.
- Opening a saved doodle always lands in Doodle Studio's Create tab, with a
  confirmation naming the doodle, because laying it out is the reason to reopen
  one.

Deleting a saved doodle asks first. It removes the only copy.

## Printing

Every PDF Doodle builds exists to be printed at an exact millimetre size, so
the button beside one opens the browser's print dialogue rather than saving a
file. The bytes are handed to the page, loaded into a hidden frame and printed
from there, which is the only route a web page has to a print dialogue.

Downloading remains available under "Nothing happened when I pressed print",
for the browsers that refuse. Wherever printing is offered, the instruction to
set Scale to 100% and turn off Fit to page goes with it: the browser's own
default rescales a PDF, which is exactly the distortion the Print scale page
exists to correct.

## Before the drawing, and after it

Anything that changes what gets drawn is asked before the drawing, on the
homepage. Putting those controls only in Doodle Studio meant the first way to
change how many pictures Doodle draws was to draw the wrong one first and pay
for it. The answers persist, because a parent drawing for the same children
wants the same answers every time.

The homepage owes those answers a home that does not cost it its shape. Below
the logo it holds one full-width element, the idea box, and the button that
acts on it; the settings are a line of small grey text under the button reading
the current answers, each one opening its choices in a floating panel. A panel
below the button turned the page into a column of same-weight boxes, which is
the look the page exists to avoid. Nothing on the homepage opens in place, so
nothing below it ever moves.

Every screen holding a doodle carries the same top bar: the logo, `Saved (n)`
and `New doodle`. Both routes are one click from the top of the page, never at
the bottom of one and inside a tab on another.

`Draw this idea again` redraws the same idea; `New doodle` returns to an empty
homepage. The two used to read `Draw another` and `New doodle`, which describe
each other.

## One idea, two readers

"Who it is for" runs from a toddler's dozen large regions to a grown-up's
hundred and fifty small ones, and it changes the drawing rather than only the
words around it: the region count, the line weight and whether decorative
pattern is welcome all come from the chosen level. Every level still obeys the
rules that make a sheet colourable, so a grown-up page is intricate but never
shaded or filled.

Ticking "Also draw one for me" draws the idea twice from one description of the
scene, once for the children and once at grown-up detail, so a family colours
the same picture at once. That is exactly two pictures whatever the number of
alternatives says, because the pair is one scene rather than several readings
of it. The children's sheet stays the doodle: changing, colouring and saving
all act on it, and the grown-up sheet is a second thing to print.

The grown-up sheet is cleaned more gently than the children's. The despeckle
pass that removes stray pixels from a bold drawing eats fine pattern work, and
thickening lines closes the smallest regions altogether.

## Colour is for the screen only

`Colour it in for me` draws a coloured copy of the doodle to look at while
colouring the printed one. It never touches the PDF: the file that prints is
always the line art, because a colouring page a child cannot colour is not one.

The coloured copy is kept for as long as the picture is unchanged, so looking
at it again is free. Changing the picture, or choosing a different alternative,
asks again, because the copy no longer matches what is on screen.
