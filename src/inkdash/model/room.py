"""Normalized per-room sensor readings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class RoomState(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    temperature: float | None = None
    humidity: float | None = None
