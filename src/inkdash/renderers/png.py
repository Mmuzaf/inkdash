"""Rasterize the dashboard SVG to an Inkplate-ready PNG.

resvg is used instead of cairo so that `uv sync` is genuinely enough to render: the wheels
are self contained, and the bundled font is passed explicitly with system fonts disabled so
output is identical on a developer laptop and inside the container.
"""

from __future__ import annotations

from io import BytesIO

import resvg_py
from PIL import Image

from inkdash.config import FONT_BOLD_PATH, FONT_FAMILY, FONT_PATH, Config
from inkdash.display import INKPLATE_PALETTE
from inkdash.model import DashboardModel
from inkdash.renderers.svg import render_svg

# Maps every possible gray to its nearest palette level, so anti-aliased glyph edges land
# on one of the eight shades the panel can actually display instead of being flattened.
_QUANTIZE_TABLE = bytes(
    min(INKPLATE_PALETTE, key=lambda level: abs(level - value)) for value in range(256)
)


def quantize(image: Image.Image) -> Image.Image:
    """Convert to grayscale and snap every pixel to the Inkplate palette."""
    return image.convert("L").point(_QUANTIZE_TABLE)


def svg_to_png(svg: str, width: int, height: int) -> Image.Image:
    raw = resvg_py.svg_to_bytes(
        svg_string=svg,
        width=width,
        height=height,
        font_files=[str(FONT_PATH), str(FONT_BOLD_PATH)],
        font_family=FONT_FAMILY,
        monospace_family=FONT_FAMILY,
        skip_system_fonts=True,
    )
    image: Image.Image = Image.open(BytesIO(bytes(raw)))
    if image.size != (width, height):
        image = image.resize((width, height), Image.Resampling.LANCZOS)
    return quantize(image)


async def render_png(
    model: DashboardModel,
    config: Config,
    layout: str | None = None,
    width: int | None = None,
    height: int | None = None,
) -> Image.Image:
    svg = await render_svg(model, config, layout)
    return svg_to_png(
        svg,
        width or config.display.width,
        height or config.display.height,
    )


def to_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
