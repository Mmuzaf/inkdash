"""The sensor panel renders rooms as a ruled table inside the double frame."""

from __future__ import annotations

from datetime import datetime

from inkdash.config import DisplayConfig
from inkdash.model import DashboardModel, InkplateState, RoomState, WeatherState
from inkdash.widgets.base import Geometry
from inkdash.widgets.canvas import FRAME
from inkdash.widgets.sensors import (
    HEADER_ROW,
    SEPARATOR_COLUMNS,
    TABLE_COLUMNS,
    SensorsPanel,
)

INKPLATE10 = Geometry.for_display(DisplayConfig())


def _model(rooms: tuple[RoomState, ...], warnings: tuple[str, ...] = ()) -> DashboardModel:
    return DashboardModel(
        generated_at=datetime(2026, 8, 11, 13, 25),
        weather=WeatherState(),
        rooms=rooms,
        inkplate=InkplateState(last_refresh=datetime(2026, 8, 11, 13, 25)),
        warnings=warnings,
    )


def _lines(rooms: tuple[RoomState, ...], warnings: tuple[str, ...] = ()) -> list[str]:
    return SensorsPanel(INKPLATE10, _model(rooms, warnings)).painted_lines


ROOMS = (
    RoomState(name="bedroom", temperature=24.8, humidity=36.0),
    RoomState(name="balcony", temperature=21.9, humidity=None),
)


def test_the_columns_fill_the_panel_exactly() -> None:
    first, last = TABLE_COLUMNS[0], TABLE_COLUMNS[-1]

    assert first.left == 1, "the frame owns column 0"
    assert last.right == INKPLATE10.right_region_width - 2, "the frame owns the last column"
    spans = sum(column.right - column.left + 1 for column in TABLE_COLUMNS)
    assert spans + len(SEPARATOR_COLUMNS) == INKPLATE10.right_region_width - 2


def test_the_header_names_every_column() -> None:
    header = _lines(ROOMS)[HEADER_ROW]

    assert "ROOM" in header
    assert "TEMP" in header
    assert "HUMIDITY" in header


def test_each_room_is_one_row_with_right_aligned_readings() -> None:
    lines = _lines(ROOMS)

    bedroom = next(line for line in lines if "BEDROOM" in line)
    assert "24.8°C" in bedroom
    assert "36%" in bedroom
    temperature = TABLE_COLUMNS[1]
    assert bedroom[temperature.right - len("24.8°C") : temperature.right] == "24.8°C"


def test_a_missing_reading_keeps_the_row() -> None:
    balcony = next(line for line in _lines(ROOMS) if "BALCONY" in line)

    assert "21.9°C" in balcony
    assert "--%" in balcony


def test_the_rules_tie_into_the_outer_frame() -> None:
    lines = _lines(ROOMS)

    rules = [line for line in lines if line.startswith(FRAME.inner_left)]
    assert len(rules) == 3, "one rule above the header, one below it, one closing the table"
    for rule in rules:
        assert rule.endswith(FRAME.inner_right)
        assert set(rule[1:-1]) <= set("─┬┼┴"), "inner rules stay single-line"


def test_every_row_is_bounded_by_the_double_frame() -> None:
    for line in _lines(ROOMS, warnings=("sensor.kitchen_temperature is unavailable",)):
        assert line[0] in {FRAME.vertical, FRAME.inner_left}
        assert line[-1] in {FRAME.vertical, FRAME.inner_right}
