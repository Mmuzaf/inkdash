"""Time series used by the chart widget."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HistoryPoint(BaseModel):
    model_config = ConfigDict(frozen=True)

    at: datetime
    value: float


class HistorySeries(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: str
    unit: str = "°C"
    points: tuple[HistoryPoint, ...] = ()

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(point.value for point in self.points)

    @property
    def minimum(self) -> float | None:
        return min(self.values) if self.points else None

    @property
    def maximum(self) -> float | None:
        return max(self.values) if self.points else None

    @property
    def average(self) -> float | None:
        values = self.values
        return sum(values) / len(values) if values else None

    @property
    def current(self) -> float | None:
        return self.points[-1].value if self.points else None
