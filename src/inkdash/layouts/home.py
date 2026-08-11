"""The default Inkplate layout: header, weather, room sensors and a 24h chart."""

from __future__ import annotations

from collections.abc import Iterable

from textual.containers import Horizontal
from textual.widget import Widget

from inkdash.layouts.base import BaseLayout, register
from inkdash.model import DashboardModel
from inkdash.widgets import ChartPanel, Rule, SensorsPanel, StatusHeader, WeatherPanel
from inkdash.widgets.base import Geometry


@register
class HomeLayout(BaseLayout):
    name = "home"

    def compose(self, model: DashboardModel) -> Iterable[Widget]:
        geometry = Geometry.for_display(self.config.display)
        yield StatusHeader(geometry, model, self.config.dashboard.title)

        panels = Horizontal(
            WeatherPanel(geometry, model),
            SensorsPanel(geometry, model, "AQARA SENSORS"),
            id="panels",
        )
        panels.styles.height = geometry.panel_height
        yield panels

        yield Rule(geometry, junction=True)
        yield ChartPanel(geometry, model.history)
        yield Rule(geometry, closing=True)
