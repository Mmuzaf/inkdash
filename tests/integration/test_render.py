"""End to end rendering: one widget tree, three outputs, one validated Inkplate image."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from inkdash.config import Config
from inkdash.display import INKPLATE_PALETTE
from inkdash.model import DashboardModel
from inkdash.renderers import render_png, render_svg, render_text

SNAPSHOT = Path(__file__).parent.parent / "snapshots" / "home.svg"


async def test_text_render_matches_the_display_grid(model: DashboardModel, config: Config) -> None:
    lines = (await render_text(model, config, "home")).splitlines()

    assert len(lines) == config.display.rows
    assert {len(line) for line in lines} == {config.display.columns}


async def test_text_render_contains_live_values(model: DashboardModel, config: Config) -> None:
    text = await render_text(model, config, "home")

    assert "STATUS" in text
    assert "BEDROOM" in text
    assert "24.8°C" in text
    assert "Battery: 82%" in text
    assert "Last Updated: 2026-08-11 13:25" in text
    assert "Awake Interval: 15 mins" in text
    assert "TEMPERATURE — BALCONY — LAST 24 HOURS" in text


async def test_svg_has_no_terminal_chrome(model: DashboardModel, config: Config) -> None:
    svg = await render_svg(model, config, "home")

    assert "<svg" in svg
    assert "circle" not in svg, "the traffic-light dots belong to Rich's window chrome"
    assert 'rx="8"' not in svg, "the rounded window frame must be gone"
    assert "DejaVu Sans Mono" in svg


async def test_svg_snapshot_is_stable(model: DashboardModel, config: Config) -> None:
    svg = await render_svg(model, config, "home")

    if os.environ.get("UPDATE_SNAPSHOTS"):
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(svg)

    assert SNAPSHOT.exists(), "run `make snapshots` to record the golden SVG"
    assert svg == SNAPSHOT.read_text(), (
        "the home layout changed; review the diff and run `make snapshots` to accept it"
    )


async def test_png_satisfies_the_inkplate_constraints(
    model: DashboardModel, config: Config
) -> None:
    image = await render_png(model, config, "home")

    assert image.size == (config.display.width, config.display.height)
    assert image.mode == "L"

    colors = image.getcolors(maxcolors=256)
    assert colors is not None
    levels = sorted(value for _count, value in colors)
    assert len(levels) <= len(INKPLATE_PALETTE)
    assert all(level in INKPLATE_PALETTE for level in levels)


async def test_png_honours_an_alternative_geometry(model: DashboardModel, config: Config) -> None:
    image = await render_png(model, config, "home", width=800, height=600)

    assert image.size == (800, 600)


@pytest.mark.parametrize("layout", ["home", "diagnostics"])
async def test_every_layout_renders(layout: str, model: DashboardModel, config: Config) -> None:
    lines = (await render_text(model, config, layout)).splitlines()

    assert len(lines) == config.display.rows
