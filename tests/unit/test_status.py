"""The header carries the device telemetry: when it last refreshed, and when it wakes next."""

from __future__ import annotations

from datetime import datetime, timedelta

from inkdash.config import DisplayConfig
from inkdash.model import DashboardModel, InkplateState, WeatherState
from inkdash.widgets.base import Geometry
from inkdash.widgets.status import StatusHeader

INKPLATE10 = Geometry.for_display(DisplayConfig())
NOW = datetime(2026, 8, 11, 17, 17)


def _title_row(inkplate: InkplateState, title: str = "STATUS") -> str:
    model = DashboardModel(generated_at=NOW, weather=WeatherState(), inkplate=inkplate)
    return StatusHeader(INKPLATE10, model, title).painted_lines[1]


def test_the_header_shows_every_field() -> None:
    row = _title_row(
        InkplateState(
            battery_percent=82,
            wifi_rssi_dbm=-55,
            last_refresh=NOW,
            next_wake=NOW + timedelta(minutes=15),
        )
    )

    assert "STATUS" in row
    assert "Last Updated: 2026-08-11 17:17" in row
    assert "Awake Interval: 15 mins" in row
    assert "WiFi -55 dBm" in row
    assert "Battery: 82%" in row


def test_the_wake_time_is_shown_as_minutes_from_now() -> None:
    row = _title_row(InkplateState(next_wake=NOW + timedelta(minutes=45, seconds=40)))

    assert "Awake Interval: 46 mins" in row, "rounded to the nearest minute"


def test_an_overdue_wake_does_not_count_backwards() -> None:
    row = _title_row(InkplateState(next_wake=NOW - timedelta(minutes=5)))

    assert "Awake Interval: 0 mins" in row


def test_absent_telemetry_is_dashed() -> None:
    row = _title_row(InkplateState())

    assert "Last Updated: --" in row
    assert "Awake Interval: -- mins" in row
    assert "WiFi --" in row
    assert "Battery: --%" in row


def test_a_long_title_cannot_overwrite_the_timestamp() -> None:
    row = _title_row(InkplateState(last_refresh=NOW), title="A VERY LONG DASHBOARD TITLE")

    assert "Last Updated: 2026-08-11 17:17" in row


def test_the_row_fits_the_display_width() -> None:
    row = _title_row(
        InkplateState(
            battery_percent=100,
            wifi_rssi_dbm=-100,
            last_refresh=NOW,
            next_wake=NOW + timedelta(minutes=999),
        )
    )

    assert len(row) == INKPLATE10.columns
    assert "Awake Interval: 999 mins" in row
    assert "Battery: 100%" in row
