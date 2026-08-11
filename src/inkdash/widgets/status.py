"""Header row and the horizontal frame rules that separate the dashboard bands."""

from __future__ import annotations

from datetime import datetime

from inkdash.model import DashboardModel
from inkdash.widgets.base import Geometry, Panel, format_percent
from inkdash.widgets.canvas import FRAME, HEADING, PRIMARY, SECONDARY, Canvas

# Anchors for the five fields of the title row, spaced for the 120 cell Inkplate 10 grid.
# Like the rest of the layout these are chosen rather than derived, so another display size
# means picking them again.
TITLE_COLUMN = 2
UPDATED_COLUMN = 16
NEXT_WAKE_COLUMN = 58
WIFI_COLUMN = 86

STAMP_FORMAT = "%Y-%m-%d %H:%M"
MISSING = "--"


class StatusHeader(Panel):
    """Top border, the title row with clock and device telemetry, then a divider rule."""

    def __init__(
        self,
        geometry: Geometry,
        model: DashboardModel,
        title: str,
        *,
        divider: bool = True,
    ) -> None:
        width = geometry.columns
        canvas = Canvas(width, geometry.header_height)

        rule = FRAME.horizontal * (width - 2)
        canvas.put(0, 0, FRAME.top_left + rule + FRAME.top_right, PRIMARY)
        canvas.put(1, 0, FRAME.vertical, PRIMARY)
        canvas.put_right(1, width, FRAME.vertical, PRIMARY)
        canvas.put(2, 0, FRAME.tee_left + rule + FRAME.tee_right, PRIMARY)
        if divider:
            canvas.put(2, geometry.divider_column, FRAME.tee_down, PRIMARY)

        inkplate = model.inkplate
        canvas.put(1, TITLE_COLUMN, title[: UPDATED_COLUMN - TITLE_COLUMN - 1], HEADING)
        canvas.put(1, UPDATED_COLUMN, f"Last Updated: {_stamp(inkplate.last_refresh)}", PRIMARY)
        canvas.put(
            1,
            NEXT_WAKE_COLUMN,
            f"Awake Interval: {_minutes_until(inkplate.next_wake, model.generated_at)} mins",
            SECONDARY,
        )

        rssi = inkplate.wifi_rssi_dbm
        wifi = f"WiFi {rssi} dBm" if rssi is not None else f"WiFi {MISSING}"
        canvas.put(1, WIFI_COLUMN, wifi, SECONDARY)
        canvas.put_right(
            1, width - 2, f"Battery: {format_percent(inkplate.battery_percent)}", PRIMARY
        )

        super().__init__(canvas, id="status-header")


def _stamp(value: datetime | None) -> str:
    return value.strftime(STAMP_FORMAT) if value else MISSING


def _minutes_until(target: datetime | None, now: datetime) -> str:
    """Whole minutes from now until the device wakes, never counting backwards."""
    if target is None:
        return MISSING
    return str(max(round((target - now).total_seconds() / 60), 0))


class Rule(Panel):
    """A single-row horizontal frame line, either between bands or closing the frame."""

    def __init__(
        self, geometry: Geometry, *, closing: bool = False, junction: bool = False
    ) -> None:
        width = geometry.columns
        canvas = Canvas(width, 1)
        left = FRAME.bottom_left if closing else FRAME.tee_left
        right = FRAME.bottom_right if closing else FRAME.tee_right
        canvas.put(0, 0, left + FRAME.horizontal * (width - 2) + right, PRIMARY)
        if junction:
            canvas.put(0, geometry.divider_column, FRAME.tee_up, PRIMARY)
        super().__init__(canvas)
