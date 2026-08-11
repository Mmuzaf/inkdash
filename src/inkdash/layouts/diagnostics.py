"""Diagnostics layout: what the provider actually returned, for debugging data sources."""

from __future__ import annotations

from collections.abc import Iterable

from textual.widget import Widget

from inkdash.layouts.base import BaseLayout, register
from inkdash.model import DashboardModel
from inkdash.widgets import Panel, Rule, StatusHeader
from inkdash.widgets.base import Geometry, format_percent, format_temperature
from inkdash.widgets.canvas import FRAME, HEADING, PRIMARY, SECONDARY, Canvas

ROOMS_ROW = 12
WARNINGS_ROW = 24


@register
class DiagnosticsLayout(BaseLayout):
    name = "diagnostics"

    def compose(self, model: DashboardModel) -> Iterable[Widget]:
        geometry = Geometry.for_display(self.config.display)
        width = geometry.columns
        body_height = geometry.body_height

        yield StatusHeader(geometry, model, "DIAGNOSTICS", divider=False)

        canvas = Canvas(width, body_height)
        for row in range(body_height):
            canvas.put(row, 0, FRAME.vertical, PRIMARY)
            canvas.put_right(row, width, FRAME.vertical, PRIMARY)

        canvas.put(0, 2, "MODEL", HEADING)
        rows = [
            ("generated_at", model.generated_at.isoformat()),
            ("weather.condition", str(model.weather.condition)),
            ("weather.temperature", format_temperature(model.weather.temperature)),
            ("forecast days", str(len(model.forecast))),
            ("rooms", str(len(model.rooms))),
            ("history points", str(len(model.history.points) if model.history else 0)),
            ("battery", str(model.inkplate.battery_percent)),
            ("wifi rssi", str(model.inkplate.wifi_rssi_dbm)),
        ]
        for index, (label, value) in enumerate(rows):
            canvas.put(2 + index, 3, label, SECONDARY)
            canvas.put(2 + index, 28, value, PRIMARY)

        canvas.put(ROOMS_ROW, 2, "ROOMS", HEADING)
        for index, room in enumerate(model.rooms[: WARNINGS_ROW - ROOMS_ROW - 2]):
            row = ROOMS_ROW + 2 + index
            canvas.put(row, 3, room.name, SECONDARY)
            canvas.put(row, 28, format_temperature(room.temperature), PRIMARY)
            canvas.put(row, 40, format_percent(room.humidity), PRIMARY)

        canvas.put(WARNINGS_ROW, 2, "WARNINGS", HEADING)
        warnings = model.warnings or ("none",)
        for index, warning in enumerate(warnings[: body_height - WARNINGS_ROW - 3]):
            canvas.put(WARNINGS_ROW + 2 + index, 3, warning[: width - 6], PRIMARY)

        yield Panel(canvas, id="diagnostics-body")
        yield Rule(geometry, closing=True)
