"""Textual widgets. A widget renders model data and never talks to a provider."""

from inkdash.widgets.base import Panel
from inkdash.widgets.chart import ChartPanel
from inkdash.widgets.sensors import SensorsPanel
from inkdash.widgets.status import Rule, StatusHeader
from inkdash.widgets.weather import WeatherPanel

__all__ = [
    "ChartPanel",
    "Panel",
    "Rule",
    "SensorsPanel",
    "StatusHeader",
    "WeatherPanel",
]
