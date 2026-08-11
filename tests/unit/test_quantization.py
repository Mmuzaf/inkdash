from __future__ import annotations

from PIL import Image

from inkdash.display import INKPLATE_PALETTE
from inkdash.renderers import quantize


def test_a_full_gradient_collapses_onto_the_palette() -> None:
    gradient = Image.new("L", (256, 1))
    gradient.putdata(list(range(256)))

    levels = set(quantize(gradient).tobytes())

    assert levels == set(INKPLATE_PALETTE)


def test_palette_values_survive_untouched() -> None:
    image = Image.new("L", (len(INKPLATE_PALETTE), 1))
    image.putdata(list(INKPLATE_PALETTE))

    assert tuple(quantize(image).tobytes()) == INKPLATE_PALETTE


def test_anti_aliased_edges_snap_to_the_nearest_shade() -> None:
    image = Image.new("L", (4, 1))
    image.putdata([17, 19, 200, 250])

    assert tuple(quantize(image).tobytes()) == (0, 36, 182, 255)


def test_rgb_input_is_converted_before_quantizing() -> None:
    image = Image.new("RGB", (1, 1), (255, 255, 255))

    result = quantize(image)

    assert result.mode == "L"
    assert result.getpixel((0, 0)) == 255
