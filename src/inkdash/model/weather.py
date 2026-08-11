"""Normalized weather state, independent of any data source."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WeatherState(BaseModel):
    model_config = ConfigDict(frozen=True)

    condition: str | None = None
    temperature: float | None = None
    high: float | None = None
    low: float | None = None
    humidity: float | None = None
    entity_name: str | None = None
    sunrise: datetime | None = None
    sunset: datetime | None = None


class ForecastDay(BaseModel):
    model_config = ConfigDict(frozen=True)

    day: str
    condition: str | None = None
    high: float | None = None
    low: float | None = None
