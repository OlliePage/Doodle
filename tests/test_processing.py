from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from colouring_factory.image_processing import analyse_line_art, normalise_line_art
from colouring_factory.models import ProcessingOptions


def _test_image() -> bytes:
    image = Image.new("RGB", (300, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((80, 50, 220, 190), outline=(70, 70, 70), width=8)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_processing_produces_binary_png_and_crops() -> None:
    output = normalise_line_art(
        _test_image(),
        ProcessingOptions(threshold=150, crop_whitespace=True, padding_percent=2),
    )
    with Image.open(BytesIO(output)) as image:
        histogram = image.convert("L").histogram()
        colours = {index for index, count in enumerate(histogram) if count}
        assert colours.issubset({0, 255})
        assert image.width < 300
        assert image.height < 220


def test_metrics_report_ink() -> None:
    output = normalise_line_art(_test_image(), ProcessingOptions(threshold=150))
    metrics = analyse_line_art(output)
    assert metrics["width_px"] > 0
    assert metrics["ink_percent"] > 0


def _faded_stroke_image() -> bytes:
    """A drawing containing both solid black and a pale stroke.

    gpt-image renders fine detail such as a hat brim in pale grey that trails
    off. The solid bar matters: with black and white both already present,
    autocontrast has no range left to stretch and cannot rescue the pale
    stroke, so the threshold alone decides whether it survives.
    """

    image = Image.new("RGB", (300, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 290, 30), fill=(0, 0, 0))
    draw.line((10, 80, 290, 80), fill=(230, 230, 230), width=4)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _stroke_survives(threshold: int) -> bool:
    output = normalise_line_art(
        _faded_stroke_image(),
        ProcessingOptions(threshold=threshold, crop_whitespace=False, thicken_pixels=0),
    )
    with Image.open(BytesIO(output)) as image:
        row = image.convert("L").crop((0, 78, 300, 82)).tobytes()
    return any(value < 128 for value in row)


def test_default_threshold_keeps_pale_strokes() -> None:
    assert _stroke_survives(ProcessingOptions().threshold)


def test_old_default_threshold_erased_pale_strokes() -> None:
    # Guards the fix: 215 is what produced the broken outlines Ollie reported.
    assert not _stroke_survives(215)


def test_the_first_run_path_takes_the_tuned_defaults() -> None:
    # The first-run path repeated the processing numbers as literals, so it kept
    # the old threshold when the tuned one was raised — on the very first picture
    # a new user sees. It must read them from ProcessingOptions instead.
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )
    quick = app_source[app_source.index("def _quick_generate") :]
    quick = quick[: quick.index("\ndef ")]

    assert "ProcessingOptions(" in quick
    assert "quick_defaults.threshold" in quick
    assert str(ProcessingOptions().threshold) not in quick, (
        "the threshold is repeated as a literal and will drift again"
    )


def test_the_studio_advances_the_seed_between_generations() -> None:
    # Recraft is the only provider given a seed. Reading the nonce without
    # advancing it returned the identical set of pictures every time the same
    # idea was submitted, with no control anywhere to break the tie.
    app_source = (Path(__file__).resolve().parents[1] / "app.py").read_text(
        encoding="utf-8"
    )
    block = app_source[app_source.index("variant_prompts = ["):]
    block = block[: block.index("st.session_state.candidates")]

    assert "generation_nonce" in block
    assert "+ 1" in block, "the studio reads the seed nonce without advancing it"
