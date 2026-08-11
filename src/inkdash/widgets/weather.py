"""Weather panel: current conditions, the forecast strip and sun times."""

from __future__ import annotations

from datetime import datetime

from inkdash.model import DashboardModel
from inkdash.widgets.base import Geometry, Panel, format_temperature
from inkdash.widgets.canvas import FRAME, HEADING, PRIMARY, SECONDARY, Canvas
from inkdash.widgets.conditions import GLYPH_HEIGHT, GLYPH_WIDTH, glyph_for
from inkdash.widgets.forecast import STRIP_HEIGHT, paint_forecast

CONDITION_ROW = 2
CONDITION_COLUMN = 2
# Clear of the current condition block, whose art starts at CONDITION_COLUMN.
TEXT_COLUMN = CONDITION_COLUMN + GLYPH_WIDTH + 2

# The strip follows the condition block directly so that the row freed up can go between the
# forecast and the sun times, where it separates two unrelated things. The block's last row
# is blank for most conditions anyway, so little is lost above.
FORECAST_ROW = CONDITION_ROW + GLYPH_HEIGHT
FORECAST_COLUMN = 3
SUN_ROW = FORECAST_ROW + STRIP_HEIGHT + 1


class WeatherPanel(Panel):
    def __init__(self, geometry: Geometry, model: DashboardModel) -> None:
        height = geometry.panel_height
        content_width = geometry.left_content_width
        canvas = Canvas(geometry.left_region_width, height)
        for row in range(height):
            canvas.put(row, 0, FRAME.vertical, PRIMARY)

        weather = model.weather
        canvas.put(0, 2, "WEATHER", HEADING)

        for offset, line in enumerate(glyph_for(weather.condition)):
            canvas.put(CONDITION_ROW + offset, CONDITION_COLUMN, line, SECONDARY)

        canvas.put(CONDITION_ROW, TEXT_COLUMN, (weather.condition or "unknown").upper(), PRIMARY)
        canvas.put(CONDITION_ROW + 1, TEXT_COLUMN, weather.entity_name or "", SECONDARY)
        canvas.put_right(
            CONDITION_ROW, content_width, format_temperature(weather.temperature), PRIMARY
        )
        canvas.put_right(
            CONDITION_ROW + 1,
            content_width,
            f"{_degrees(weather.high)} / {_degrees(weather.low)}",
            SECONDARY,
        )

        paint_forecast(canvas, FORECAST_ROW, FORECAST_COLUMN, model.forecast)

        canvas.put(SUN_ROW, 2, "SUN", HEADING)
        canvas.put(SUN_ROW, 10, f"↑ {_clock(weather.sunrise)}", PRIMARY)
        canvas.put(SUN_ROW, 24, f"↓ {_clock(weather.sunset)}", PRIMARY)

        super().__init__(canvas, id="weather-panel")


def _degrees(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "--"


def _clock(value: datetime | None) -> str:
    return value.strftime("%H:%M") if value else "--:--"
