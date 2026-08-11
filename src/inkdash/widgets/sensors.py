"""Room sensor table. Device telemetry lives in the header, not here."""

from __future__ import annotations

from dataclasses import dataclass

from inkdash.model import DashboardModel, RoomState
from inkdash.widgets.base import Geometry, Panel, format_temperature
from inkdash.widgets.canvas import FRAME, HEADING, PRIMARY, SECONDARY, Canvas


@dataclass(frozen=True)
class Column:
    """One table column, as the inclusive span of cells it owns."""

    label: str
    left: int
    right: int
    align_right: bool = False


# Spans for the 40 cell sensor panel: the outer frame owns columns 0 and 39, so the table
# fills 1 to 38 with a single-line separator between neighbouring columns. The panel is this
# narrow because the forecast strip next to it needs the width more than a room name does.
TABLE_COLUMNS = (
    Column("ROOM", 1, 16),
    Column("TEMP", 18, 27, align_right=True),
    Column("HUMIDITY", 29, 38, align_right=True),
)
SEPARATOR_COLUMNS = tuple(column.right + 1 for column in TABLE_COLUMNS[:-1])

HEAD_RULE_ROW = 1
HEADER_ROW = 2
BODY_RULE_ROW = 3
FIRST_ROOM_ROW = 4
MAX_ROOMS = 6

# Inner rules are single-line so the table reads as a subdivision of the double frame.
RULE = "─"
COLUMN_EDGE = "│"
TOP_JUNCTION = "┬"
CROSS_JUNCTION = "┼"
BOTTOM_JUNCTION = "┴"


class SensorsPanel(Panel):
    def __init__(self, geometry: Geometry, model: DashboardModel, title: str = "SENSORS") -> None:
        height = geometry.panel_height
        width = geometry.right_region_width
        canvas = Canvas(width, height)
        for row in range(height):
            canvas.put(row, 0, FRAME.vertical, PRIMARY)
            canvas.put_right(row, width, FRAME.vertical, PRIMARY)

        canvas.put(0, 2, title, HEADING)

        rooms = model.rooms[:MAX_ROOMS]
        _rule(canvas, HEAD_RULE_ROW, width, TOP_JUNCTION)
        _rule(canvas, BODY_RULE_ROW, width, CROSS_JUNCTION)
        _rule(canvas, FIRST_ROOM_ROW + len(rooms), width, BOTTOM_JUNCTION)

        _separators(canvas, HEADER_ROW)
        for column in TABLE_COLUMNS:
            _cell(canvas, HEADER_ROW, column, column.label, HEADING)

        for index, room in enumerate(rooms):
            row = FIRST_ROOM_ROW + index
            _separators(canvas, row)
            _cell(canvas, row, TABLE_COLUMNS[0], room.name.upper(), PRIMARY)
            _cell(canvas, row, TABLE_COLUMNS[1], format_temperature(room.temperature), PRIMARY)
            _cell(canvas, row, TABLE_COLUMNS[2], _humidity(room), SECONDARY)

        if model.warnings:
            canvas.put_right(
                height - 2,
                geometry.right_content_width,
                f"{len(model.warnings)} source warnings",
                SECONDARY,
            )

        super().__init__(canvas, id="sensors-panel")


def _rule(canvas: Canvas, row: int, width: int, junction: str) -> None:
    """Draw a table rule across the panel, tied into the outer frame at both ends."""
    cells = [RULE] * (width - 2)
    for column in SEPARATOR_COLUMNS:
        cells[column - 1] = junction
    canvas.put(row, 0, FRAME.inner_left + "".join(cells) + FRAME.inner_right, PRIMARY)


def _separators(canvas: Canvas, row: int) -> None:
    for column in SEPARATOR_COLUMNS:
        canvas.put(row, column, COLUMN_EDGE, PRIMARY)


def _cell(canvas: Canvas, row: int, column: Column, text: str, shade: int) -> None:
    if column.align_right:
        canvas.put_right(row, column.right, text, shade)
    else:
        canvas.put(row, column.left + 1, text[: column.right - column.left - 1], shade)


def _humidity(room: RoomState) -> str:
    return f"{room.humidity:.0f}%" if room.humidity is not None else "--%"
