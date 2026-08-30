# Doodle

Doodle is a local web app for turning a plain-English idea into a toddler-friendly colouring picture and exporting it at exact physical dimensions.

Its opening screen is deliberately spare: the Doodle wordmark and one prompt bar. Type an idea such as:

> A smiling baby dinosaur washing a toy fire engine

Press Enter to open the studio with that idea already loaded.

![Doodle homepage](HOMEPAGE_PREVIEW.png)

The application keeps two jobs separate:

- The image model invents the drawing.
- The layout engine controls the PDF page, circles, margins, spacing and captions in millimetres.

## What is included

- Minimal Doodle homepage
- OpenAI image generation through the Images API
- Three original offline demo drawings
- PNG, JPG and WebP upload
- Strict black-and-white conversion
- Adjustable threshold, speck removal, whitespace crop and line thickening
- A4 portrait or landscape colouring pages
- A4 sheets of repeated circular designs
- Separate finished, paper-cut and safe-area badge diameters
- Custom-size PDF pages
- Optional captions added as proper PDF text
- PDF preview and download
- Local saved-doodle library
- Printer calibration with optional horizontal and vertical compensation
- Automated tests for geometry and PDF page boxes

## Fastest start on macOS

1. Install Python 3.11 or later if it is not already available.
2. Unzip this folder.
3. Open Terminal, type `cd `, drag the unzipped folder into Terminal, and press Return.
4. Run:

```bash
./run.command
```

The first launch creates a private `.venv`, installs the dependencies and opens Doodle in your browser. Later launches use the same command.

You can also double-click `run.command`. macOS may require **Control-click → Open** on the first launch.

## Windows

Double-click:

```text
run_windows.bat
```

## Manual start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Using the homepage

The homepage contains no settings, menus or explanation. It presents only:

- the Doodle wordmark;
- one prompt bar.

Enter a picture idea and press Return. Doodle then opens the working studio with the idea carried into the generation form.

Use **New doodle** in the studio to return to the clean homepage.

Desktop and mobile visual previews are included in the `samples/` folder.

## AI generation

Enter your OpenAI API key in the collapsed **Settings** sidebar or set it before launch:

```bash
export OPENAI_API_KEY="your-key-here"
./run.command
```

The key is held in the running app session and is not written to the saved-doodle library. Demo and upload modes work without an API key.

AI artwork is probabilistic: the same words can produce a different illustration. Print geometry remains deterministic.

## Badge dimensions

A nominal 58 mm badge can involve three distinct measurements:

- **Finished face:** the visible front of the completed badge.
- **Paper cut diameter:** the disc cut from the printed sheet. Some presses require extra paper to wrap around the shell.
- **Safe artwork diameter:** the central area in which faces, eyes and text should remain.

Do not assume the paper cut is 58 mm. Use the template supplied with the badge press.

With a 58 mm cut, 10 mm A4 margins and 5 mm gaps, the default grid holds twelve circles: three columns by four rows.

## Printing at scale

1. Download the PDF rather than printing the browser preview.
2. Choose **Actual size** or **100%** in the print dialogue.
3. Disable **Fit**, **Shrink oversized pages** and **Scale to printable area**.
4. Print one calibration page and measure it before making a batch.

For example, a 100 mm line that prints as 98.6 mm needs this correction:

```text
100 / 98.6 = 1.0142, or 101.42%
```

Doodle can store separate horizontal and vertical corrections.

## Local data

By default, saved doodles and calibration settings live at:

```text
~/.doodle
```

Override the location with:

```bash
export DOODLE_DATA_DIR="/your/chosen/folder"
```

For compatibility, an existing `~/.colouring_factory` library is retained when no `~/.doodle` folder exists.

## Run the tests

```bash
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

The tests cover, among other things:

- A4 PDF MediaBox dimensions
- exact custom PDF dimensions
- 58 mm circle-grid capacity
- printer-compensation mathematics
- binary black-and-white output
- all three main application layout branches

## Repository structure

```text
app.py                         Doodle interface
colouring_factory/
  calibration.py              Printer compensation
  demo.py                     Built-in artwork catalogue
  generators.py               AI image provider
  image_processing.py         Black-and-white clean-up
  layouts.py                  Millimetre geometry and grids
  models.py                   Typed configuration objects
  pdf_export.py               PDF creation
  preview.py                  PDF-to-PNG preview
  prompts.py                  Colouring-art prompt factory
  storage.py                  Saved doodles and settings
assets/                       Original demo line art
samples/                      Ready-made outputs
scripts/                      Sample-generation utility
tests/                        Geometry, export and smoke tests
```

## MVP boundaries

- Generated artwork is raster PNG rather than editable vector SVG.
- A free-form image model may alter a recurring character between generations.
- Anatomical and complexity scoring is not automated; you choose the acceptable picture visually.
- Calibration corrects generated content dimensions but cannot remove a printer's hard non-printable margins.
