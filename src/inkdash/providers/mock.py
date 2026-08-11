"""Fixture-backed provider so the dashboard works without any external service."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from inkdash.model import (
    DashboardModel,
    ForecastDay,
    HistoryPoint,
    HistorySeries,
    InkplateState,
    RoomState,
    WeatherState,
)


class MockProvider:
    """Loads a YAML fixture. Deterministic by construction: no clock, no randomness."""

    name = "mock"

    def __init__(self, fixture: Path) -> None:
        self.fixture = fixture

    async def load(self) -> DashboardModel:
        return self.load_sync()

    def load_sync(self) -> DashboardModel:
        if not self.fixture.exists():
            raise FileNotFoundError(
                f"Mock fixture not found: {self.fixture}. Set dashboard.mock_fixture in your "
                "config, or switch dashboard.provider to home_assistant."
            )
        raw: dict[str, Any] = yaml.safe_load(self.fixture.read_text()) or {}
        return DashboardModel(
            generated_at=datetime.fromisoformat(raw["generated_at"]),
            weather=WeatherState.model_validate(raw.get("weather", {})),
            forecast=tuple(ForecastDay.model_validate(day) for day in raw.get("forecast", [])),
            rooms=tuple(
                RoomState(name=name, **(values or {}))
                for name, values in (raw.get("rooms") or {}).items()
            ),
            inkplate=InkplateState.model_validate(raw.get("inkplate", {})),
            history=_build_history(raw.get("history")),
        )


def _build_history(raw: dict[str, Any] | None) -> HistorySeries | None:
    if not raw:
        return None
    start = datetime.fromisoformat(raw["start"])
    step = timedelta(minutes=raw.get("interval_minutes", 30))
    points = tuple(
        HistoryPoint(at=start + step * index, value=float(value))
        for index, value in enumerate(raw.get("values", []))
    )
    return HistorySeries(
        label=raw.get("label", "HISTORY"),
        unit=raw.get("unit", "°C"),
        points=points,
    )
