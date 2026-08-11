"""Normalized domain objects shared by every provider, layout and renderer."""

from inkdash.model.dashboard import DashboardModel
from inkdash.model.device import InkplateState
from inkdash.model.history import HistoryPoint, HistorySeries
from inkdash.model.room import RoomState
from inkdash.model.weather import ForecastDay, WeatherState

__all__ = [
    "DashboardModel",
    "ForecastDay",
    "HistoryPoint",
    "HistorySeries",
    "InkplateState",
    "RoomState",
    "WeatherState",
]
