"""Interactive terminal rendering."""

from __future__ import annotations

import shutil
import sys

from inkdash.app import DashboardApp
from inkdash.config import Config
from inkdash.model import DashboardModel


def run_console(model: DashboardModel, config: Config, layout: str | None = None) -> None:
    """Start the interactive Textual dashboard."""
    _warn_if_terminal_is_too_small(config)
    DashboardApp(model, config, layout).run()


def _warn_if_terminal_is_too_small(config: Config) -> None:
    """The dashboard has fixed geometry, so a small terminal silently crops it."""
    size = shutil.get_terminal_size()
    columns, rows = config.display.columns, config.display.rows
    if size.columns < columns or size.lines < rows:
        print(
            f"Terminal is {size.columns}x{size.lines}; the dashboard is drawn at "
            f"{columns}x{rows} and will be cropped. Resize, or use `inkdash render`.",
            file=sys.stderr,
        )
