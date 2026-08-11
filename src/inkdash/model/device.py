"""Normalized Inkplate device telemetry."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InkplateState(BaseModel):
    model_config = ConfigDict(frozen=True)

    battery_percent: int | None = None
    wifi_rssi_dbm: int | None = None
    last_refresh: datetime | None = None
    next_wake: datetime | None = None
