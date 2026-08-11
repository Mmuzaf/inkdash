"""Render targets. All of them consume the same Textual screen."""

from inkdash.renderers.console import run_console
from inkdash.renderers.png import quantize, render_png, svg_to_png, to_bytes
from inkdash.renderers.svg import render_svg, render_text

__all__ = [
    "quantize",
    "render_png",
    "render_svg",
    "render_text",
    "run_console",
    "svg_to_png",
    "to_bytes",
]
