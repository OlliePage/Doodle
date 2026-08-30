from io import BytesIO

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
