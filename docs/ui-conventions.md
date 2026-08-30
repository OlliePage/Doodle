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
- The homepage offers `Your saved doodles (n)` once there is at least one, and
  stays a single idea box before that.
- Opening a saved doodle always lands in Doodle Studio's Create tab, with a
  confirmation naming the doodle, because laying it out is the reason to reopen
  one.

Deleting a saved doodle asks first. It removes the only copy.
