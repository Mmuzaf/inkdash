from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from inkdash.model import DashboardModel, HistoryPoint, HistorySeries, RoomState


def test_fixture_parses_into_model(model: DashboardModel) -> None:
    assert model.weather.condition == "cloudy"
    assert model.weather.temperature == pytest.approx(19.7)
    assert len(model.forecast) == 6
    assert model.forecast[0].day == "TUE"
    assert {room.name for room in model.rooms} == {"bedroom", "bathroom", "kitchen", "balcony"}
    assert model.inkplate.battery_percent == 82
    assert model.inkplate.wifi_rssi_dbm == -55


def test_room_lookup_is_case_insensitive(model: DashboardModel) -> None:
    room = model.room("BEDROOM")
    assert room is not None
    assert room.temperature == pytest.approx(24.8)
    assert model.room("cellar") is None


def test_measurements_are_optional_so_a_degraded_source_still_renders() -> None:
    room = RoomState(name="attic")
    assert room.temperature is None
    assert room.humidity is None


def test_model_is_frozen(model: DashboardModel) -> None:
    with pytest.raises(ValidationError):
        model.rooms = ()  # type: ignore[misc]


def test_history_statistics() -> None:
    series = HistorySeries(label="BALCONY", points=_points([15.0, 20.0, 25.0]))
    assert series.minimum == 15.0
    assert series.maximum == 25.0
    assert series.average == pytest.approx(20.0)
    assert series.current == 25.0


def test_empty_history_has_no_statistics() -> None:
    series = HistorySeries(label="EMPTY")
    assert series.minimum is None
    assert series.average is None
    assert series.current is None


def _points(values: list[float]) -> tuple[HistoryPoint, ...]:
    start = datetime(2026, 8, 11, 12, 0)
    return tuple(
        HistoryPoint(at=start + timedelta(minutes=30 * index), value=value)
        for index, value in enumerate(values)
    )
