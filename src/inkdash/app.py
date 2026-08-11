"""The Textual application shared by the console, SVG and PNG renderers.

There is exactly one widget tree. Every render target consumes the same screen, so the
terminal preview and the e-paper image can never drift apart.
"""

from __future__ import annotations

from collections.abc import Iterable

from textual.app import App, ComposeResult
from textual.widget import Widget

from inkdash.config import Config
from inkdash.display import PALETTE_HEX
from inkdash.layouts import get_layout
from inkdash.model import DashboardModel


class DashboardApp(App[None]):
    """Renders one model through one layout at the fixed dashboard geometry."""

    CSS = f"""
    Screen {{
        background: {PALETTE_HEX[7]};
        color: {PALETTE_HEX[0]};
        overflow: hidden;
    }}
    Static {{
        background: {PALETTE_HEX[7]};
    }}
    #panels {{
        layout: horizontal;
    }}
    """

    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh", "Refresh")]

    def __init__(self, model: DashboardModel, config: Config, layout: str | None = None) -> None:
        super().__init__()
        self.model = model
        self.config = config
        self.layout_name = layout or config.dashboard.layout

    def compose(self) -> ComposeResult:
        layout = get_layout(self.layout_name)(self.config)
        widgets: Iterable[Widget] = layout.compose(self.model)
        yield from widgets
