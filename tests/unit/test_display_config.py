"""Display selection: naming a model is the whole configuration, everything else is fixed."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from inkdash.config import Config, DisplayConfig
from inkdash.display import DISPLAY_PROFILES
from inkdash.widgets.base import LAYOUTS, Geometry
from inkdash.widgets.forecast import STRIP_HEIGHT, strip_width
from inkdash.widgets.weather import FORECAST_COLUMN, FORECAST_ROW, SUN_ROW


def test_the_default_display_is_an_inkplate_10() -> None:
    display = DisplayConfig()

    assert display.model == "inkplate10"
    assert (display.width, display.height) == (1200, 825)
    assert (display.columns, display.rows) == (120, 42)
    assert display.grayscale_levels == 8


def test_one_character_cell_is_ten_by_nineteen_px() -> None:
    display = DisplayConfig()

    assert display.cell_width == 10.0
    assert round(display.cell_height, 2) == 19.64


def test_an_unknown_model_is_rejected_with_the_supported_ones() -> None:
    with pytest.raises(ValidationError, match="inkplate10"):
        DisplayConfig(model="inkplate6")


def test_geometry_cannot_be_overridden_in_the_config() -> None:
    with pytest.raises(ValidationError, match="width"):
        Config.model_validate({"display": {"model": "inkplate10", "width": 800}})


@pytest.mark.parametrize("model", sorted(DISPLAY_PROFILES))
def test_every_display_has_a_layout_that_fills_its_grid(model: str) -> None:
    display = DisplayConfig(model=model)
    geometry = Geometry.for_display(display)

    assert (geometry.columns, geometry.rows) == (display.columns, display.rows)
    bands = geometry.header_height + geometry.panel_height + geometry.chart_height + 2
    assert bands == geometry.rows, "header, panels, chart and the two rules must fill the grid"
    assert 0 < geometry.divider_column < geometry.columns


def test_the_inkplate_10_bands_are_the_ones_the_widgets_expect() -> None:
    geometry = LAYOUTS["inkplate10"]

    assert geometry.divider_column == 80
    assert geometry.panel_height == 19
    assert geometry.chart_height == 18
    assert geometry.body_height == 38


def test_the_weather_panel_has_room_for_a_full_forecast_strip() -> None:
    """Why the divider sits at 80: six condition blocks have to fit beside the sensors."""
    geometry = LAYOUTS["inkplate10"]

    assert FORECAST_COLUMN + strip_width(6) <= geometry.left_content_width
    assert FORECAST_ROW + STRIP_HEIGHT <= SUN_ROW, "the strip may not run into the sun times"
    assert SUN_ROW < geometry.panel_height, "the sun times have to land inside the panel"


def test_a_display_without_a_layout_says_so() -> None:
    unsupported = DisplayConfig.model_construct(model="inkplate6")

    with pytest.raises(ValueError, match="No dashboard geometry for inkplate6"):
        Geometry.for_display(unsupported)
