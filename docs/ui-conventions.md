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
- Adding someone to the cast, and redrawing an existing character's portrait,
  both stay on the characters screen with a confirmation naming who changed.
  Neither is a doodle: a saved character with no route back to a printable
  copy of their portrait once looked like one, headed "Your Doodle is ready"
  with buttons that made no sense for a face with no scene behind it. Every
  character tile carries its own `Open as a doodle` button instead, which
  costs nothing and works for a character added weeks ago as well as one
  just drawn.

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

## Who's in the picture

Three decisions from adding a saved cast of characters, recorded so a later
change has to argue with them rather than quietly undo them.

- The homepage settings line names a count, `3 characters`, never the
  characters themselves. That line is a row of two-or-three-word popovers
  built specifically to stay one row regardless of how many pictures Doodle
  can draw; a cast of names would grow with every character added and break
  the row it sits in. Opening the popover still lists every name, with a
  checkbox each, so nothing is hidden — only the closed line stays short.
- A person is always drawn at full facial fidelity, with no setting to turn
  it down. Whenever any character in a scene is a person, the prompt exempts
  their head from the reader's line profile, so a toddler sheet's few, large,
  simple shapes still leave a face carrying as much fine line work as it
  takes to be recognisably them. A face that is not recognisable has failed
  at the one job it had, at any age level.
- Every picture Doodle makes reaches the badge machinery the same way: it
  becomes `quick_processed`, and the badge strip looks up (or builds) its own
  fit from whatever `quick_processed` currently is. A newly drawn character's
  portrait, a redraw, a refinement and an earlier version picked back up from
  the version strip all pass through that one door; nothing sets the badge
  preview directly, so nothing can leave it pointing at a picture no longer
  on screen.
- Unlike `Saved doodles (n)` in the corner, the characters popover is not
  hidden until there is something to show. Copying that rule here once left
  no control anywhere on a clean install that reached the characters screen,
  so a parent could never add their first character. It renders from the
  first run, inviting the parent to add someone, and is hidden only when the
  active drawing service declares it cannot look at a reference picture at
  all — in which case nothing behind the control could work regardless of
  what is saved.
- A doodle records which characters it was actually drawn with, on the
  artwork's own metadata, rather than the badge redraw reading whoever
  happens to be ticked when that button is pressed. Ticking someone after a
  picture is drawn — a sample, or an ordinary idea drawn with no cast — must
  never put them into a redraw of a picture that never had them.
- Two characters sharing a name is allowed by design — a girl and her teddy
  may both be called Ida — so saving one does not ask for confirmation or
  block the save. It does say so afterwards, plainly, because six identical
  entries from one accident is a different problem from two deliberate
  ones, and only the parent can tell the two apart.

## Paid controls cannot fire twice from one press

Every button that spends a generation sets a session-state flag before it
calls out and clears it in a `finally`, whatever the call's own name for the
flag (`busy_add_character`, `busy_redraw_<id>`, and so on). Streamlit can
queue a click made while that same control's previous press is still
blocked in the call, and replay it the moment the call returns; without the
flag, a parent who pressed a silent-looking button a second time paid for a
second picture, and once for a second saved character. The flag is checked
before the call starts and always released afterwards, success or failure,
so a failed call leaves its button pressable again rather than wedged shut
for the rest of the session. Every such button also names what it is doing
while it runs, in `st.spinner`, because a button with no visible effect is
indistinguishable from a broken one and invites exactly the second press
this guard exists to survive.
