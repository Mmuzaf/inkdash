"""SVG export of the Textual screen, without the fake terminal window.

Rich's default SVG template wraps the output in a macOS-style window with rounded corners,
a title bar and traffic-light dots. The template here drops the `{chrome}` variable and
sizes the character cell from the configured panel, so rasterizing to that panel's
resolution introduces no glyph stretching.
"""

from __future__ import annotations

import io

from rich.console import Console
from rich.terminal_theme import TerminalTheme

from inkdash.app import DashboardApp
from inkdash.config import FONT_FAMILY, Config, DisplayConfig
from inkdash.display import PALETTE_HEX
from inkdash.model import DashboardModel

# Rich fixes the character box at 20px with a line height of 1.22x.
CHAR_HEIGHT = 20.0
LINE_HEIGHT_RATIO = 1.22
# DejaVu Sans Mono advances 0.6 em per glyph.
FONT_ADVANCE = 0.6


def font_aspect_ratio(display: DisplayConfig) -> float:
    """Width-to-height ratio of one character box for the configured panel.

    Deriving this from the panel geometry means the natural SVG box already has the display
    aspect ratio, so rasterizing to the panel size introduces no glyph stretching.
    """
    return (display.cell_width / display.cell_height) * LINE_HEIGHT_RATIO


def font_size(display: DisplayConfig) -> float:
    """Font size that makes the natural glyph advance match the cell width.

    Needed because a rasterizer may ignore the textLength attribute Rich emits.
    """
    return CHAR_HEIGHT * font_aspect_ratio(display) / FONT_ADVANCE


# Pure black on pure white: the layout picks its own palette shades per glyph.
INKPLATE_THEME = TerminalTheme(
    (255, 255, 255),
    (0, 0, 0),
    [(0, 0, 0)] * 8,
    [(0, 0, 0)] * 8,
)


def _svg_template(display: DisplayConfig) -> str:
    # The whole matrix is bold: thin stems lose too much contrast on e-paper, and the runs
    # Rich emits carry an explicit textLength, so the heavier face cannot shift the grid.
    return f"""<svg class="{{unique_id}}-matrix" \
xmlns="http://www.w3.org/2000/svg" \
viewBox="0 0 {{terminal_width}} {{terminal_height}}" \
width="{{terminal_width}}" height="{{terminal_height}}" preserveAspectRatio="none">
<style>
.{{unique_id}}-matrix {{{{
    font-family: "{FONT_FAMILY}", monospace;
    font-size: {font_size(display):.4f}px;
    font-weight: bold;
}}}}
{{styles}}
</style>
<rect width="100%" height="100%" fill="{PALETTE_HEX[7]}"/>
<defs>
{{lines}}
</defs>
{{backgrounds}}
<g class="{{unique_id}}-matrix">
{{matrix}}
</g>
</svg>
"""


def record_screen(app: DashboardApp) -> Console:
    """Render the running app's screen into a recording Rich console.

    Mirrors what App.export_screenshot does internally, so that a custom SVG template can
    be supplied and the same recording can also be exported as plain text.
    """
    console = Console(
        width=app.size.width,
        height=app.size.height,
        file=io.StringIO(),
        force_terminal=True,
        color_system="truecolor",
        record=True,
        legacy_windows=False,
        safe_box=False,
    )
    console.print(
        app.screen._compositor.render_update(full=True, screen_stack=app._background_screens)
    )
    return console


async def render_svg(
    model: DashboardModel,
    config: Config,
    layout: str | None = None,
) -> str:
    """Run the dashboard headlessly at the display grid size and export it as SVG."""
    app = DashboardApp(model, config, layout)
    async with app.run_test(size=(config.display.columns, config.display.rows)) as pilot:
        await pilot.pause()
        console = record_screen(app)
    return console.export_svg(
        theme=INKPLATE_THEME,
        code_format=_svg_template(config.display),
        font_aspect_ratio=font_aspect_ratio(config.display),
        unique_id="inkdash",
    )


async def render_text(
    model: DashboardModel,
    config: Config,
    layout: str | None = None,
) -> str:
    """Plain text export of the same screen."""
    app = DashboardApp(model, config, layout)
    async with app.run_test(size=(config.display.columns, config.display.rows)) as pilot:
        await pilot.pause()
        console = record_screen(app)
    return console.export_text()
