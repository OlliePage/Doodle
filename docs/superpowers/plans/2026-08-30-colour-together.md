# Colour together: detail levels and a matching grown-up sheet

**Goal:** One idea produces a sheet a toddler can colour and a sheet a grown-up
wants to colour, both showing the same scene, so a family can colour together.

**Approach:** The drawing rules that vary by reader already live in one table
keyed by the "who it is for" setting. That table gains two rungs and a richer
shape; the pairing draws one scene twice at two levels rather than drawing two
unrelated pictures.

**Decided with Ollie on 2026-08-30:** four levels rather than three, because a
six-year-old is bored by the 4-5 sheet and defeated by an adult one. The pair
is planned together from one scene description rather than derived by adding
detail to the child's finished drawing, which risks thickening its outlines.

## Levels

| Level | Regions | Lines | Texture |
|---|---|---|---|
| 2-3 years | 6–12 | very thick, rounded | none |
| 4-5 years | 12–28 | thick | simple props and clothing |
| 6-9 years | 30–60 | medium, even | simple repeated patterns |
| Grown-up | 150+ | fine, even | dense decorative fills, mandala density |

Every level keeps the rules that make a sheet colourable: pure white
background, black line only, no grey, shading or gradients, every region
closed. The grown-up level relaxes only the ban on pattern and fine detail.

## Tasks

- [x] 1. `prompts.py`: a `DetailLevel` record and the four levels, replacing
  `AGE_RULES`. The prompt's audience line, region guidance, line weight and
  texture rule all come from the level. `build_refinement_prompt` uses the
  same table so a change to a grown-up sheet stays a grown-up sheet.
- [x] 2. `storage.py`: four choices, and a remembered `quick_pair_grown_up`
  flag. An unrecognised level still falls back to the toddler one.
- [x] 3. Homepage: the level control gains the two new rungs, and a tick
  reading "Also draw one for me, at grown-up detail" inside the same popover,
  hidden when the chosen level is already Grown-up. The settings line says
  "2-3 years + grown-up" when the pair is on.
- [x] 4. Generation: with the pair on, one scene is drawn twice, at the chosen
  level and at Grown-up, and the alternatives count is not used, so the cost is
  exactly two pictures. The grown-up sheet is cleaned more gently, because the
  despeckle pass that tidies a toddler drawing eats fine pattern work.
- [x] 5. Result screen: the grown-up sheet appears below the child's with its
  own print button and download fallback. Every existing control keeps acting
  on the child's sheet.
- [x] 6. Tests: the four levels produce different prompts; a grown-up prompt
  permits pattern and never calls its reader a young child, while still
  forbidding grey and shading; ticking the box draws two sheets from one scene
  and leaves the child's PDF untouched; without it nothing changes.
