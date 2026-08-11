"""Layout contract and registry.

A layout turns a DashboardModel into widgets. It must never query a data source, so
swapping `layout: home` for `layout: diagnostics` requires no backend change.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from textual.widget import Widget

from inkdash.config import Config
from inkdash.model import DashboardModel


class Layout(Protocol):
    name: str

    def __init__(self, config: Config) -> None: ...

    def compose(self, model: DashboardModel) -> Iterable[Widget]: ...


class BaseLayout:
    """Convenience base carrying the config."""

    name = "base"

    def __init__(self, config: Config) -> None:
        self.config = config

    def compose(self, model: DashboardModel) -> Iterable[Widget]:
        raise NotImplementedError


LAYOUTS: dict[str, type[BaseLayout]] = {}


def register(layout: type[BaseLayout]) -> type[BaseLayout]:
    LAYOUTS[layout.name] = layout
    return layout


def get_layout(name: str) -> type[BaseLayout]:
    try:
        return LAYOUTS[name]
    except KeyError:
        available = ", ".join(sorted(LAYOUTS)) or "none"
        raise ValueError(f"Unknown layout: {name!r}. Available layouts: {available}") from None


def list_layouts() -> list[str]:
    return sorted(LAYOUTS)
