"""Pluggable layouts. Importing this package registers the built-in layouts."""

from inkdash.layouts import diagnostics, home  # noqa: F401  (import registers the layouts)
from inkdash.layouts.base import LAYOUTS, BaseLayout, Layout, get_layout, list_layouts, register

__all__ = [
    "LAYOUTS",
    "BaseLayout",
    "Layout",
    "get_layout",
    "list_layouts",
    "register",
]
