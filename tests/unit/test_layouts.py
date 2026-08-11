from __future__ import annotations

import pytest

from inkdash.config import Config
from inkdash.controllers import build_provider
from inkdash.layouts import get_layout, list_layouts
from inkdash.layouts.home import HomeLayout


def test_builtin_layouts_are_registered() -> None:
    assert "home" in list_layouts()
    assert "diagnostics" in list_layouts()


def test_get_layout_returns_the_class() -> None:
    assert get_layout("home") is HomeLayout


def test_unknown_layout_names_the_alternatives() -> None:
    with pytest.raises(ValueError, match="Available layouts"):
        get_layout("nope")


def test_unknown_provider_is_rejected(config: Config) -> None:
    with pytest.raises(ValueError, match="Available providers"):
        build_provider(config, "carrier-pigeon")
