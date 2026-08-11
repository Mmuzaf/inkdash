"""The aggregate model every layout renders from."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from inkdash.model.device import InkplateState
from inkdash.model.history import HistorySeries
from inkdash.model.room import RoomState
from inkdash.model.weather import ForecastDay, WeatherState


class DashboardModel(BaseModel):
    """Everything a layout is allowed to know about."""

    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    weather: WeatherState = Field(default_factory=WeatherState)
    forecast: tuple[ForecastDay, ...] = ()
    rooms: tuple[RoomState, ...] = ()
    inkplate: InkplateState = Field(default_factory=InkplateState)
    history: HistorySeries | None = None
    warnings: tuple[str, ...] = ()

    def room(self, name: str) -> RoomState | None:
        for room in self.rooms:
            if room.name.casefold() == name.casefold():
                return room
        return None
