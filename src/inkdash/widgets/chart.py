"""Block-filled area chart for a history series.

Each column is filled from the baseline with solid block glyphs, and the topmost cell uses
a partial block. That puts the crest on one of eight sub-rows, so a nine row plot resolves
values it could not with one glyph per row. Solid blocks rather than the shaded ░▒▓ glyphs:
those are dither patterns, and dithering is what makes small type mushy on e-paper. Depth
comes from the palette instead, a dark crest over a lighter body.
"""

from __future__ import annotations

from dataclasses import dataclass

from inkdash.model import HistorySeries
from inkdash.widgets.base import Geometry, Panel
from inkdash.widgets.canvas import (
    ANNOTATION,
    AXIS,
    FRAME,
    GRID,
    HEADING,
    PRIMARY,
    SECONDARY,
    Canvas,
)

AXIS_COLUMN = 7
PLOT_LEFT = 9
PLOT_TOP = 3
TIME_TICKS = 6
STAT_SPACING = 24

# One eighth of a cell through to a full cell, growing from the bottom edge.
EIGHTH_BLOCKS = "▁▂▃▄▅▆▇█"
FULL_BLOCK = EIGHTH_BLOCKS[-1]
SUB_ROWS = len(EIGHTH_BLOCKS)
AREA_SHADE = AXIS
# Rows between the last plotted row and the bottom of the panel: the axis, the time ticks,
# a blank row, the summary row and a blank margin.
BOTTOM_BLOCK = 7


@dataclass(frozen=True)
class ChartFrame:
    """Plot area of the chart, in cells, positioned inside the chart band."""

    columns: int
    height: int

    @classmethod
    def from_geometry(cls, geometry: Geometry) -> ChartFrame:
        return cls(columns=geometry.columns, height=geometry.chart_height)

    @property
    def plot_right(self) -> int:
        return self.columns - 3

    @property
    def plot_width(self) -> int:
        return self.plot_right - PLOT_LEFT + 1

    @property
    def plot_bottom(self) -> int:
        return self.height - BOTTOM_BLOCK

    @property
    def plot_rows(self) -> int:
        return self.plot_bottom - PLOT_TOP + 1

    @property
    def axis_row(self) -> int:
        return self.plot_bottom + 1

    @property
    def ticks_row(self) -> int:
        return self.axis_row + 1

    @property
    def stats_row(self) -> int:
        return self.ticks_row + 2


class ChartPanel(Panel):
    """Renders a series as a filled area with axis, time ticks and a summary row."""

    def __init__(self, geometry: Geometry, series: HistorySeries | None) -> None:
        frame = ChartFrame.from_geometry(geometry)
        canvas = Canvas(frame.columns, frame.height)
        for row in range(frame.height):
            canvas.put(row, 0, FRAME.vertical, PRIMARY)
            canvas.put_right(row, frame.columns, FRAME.vertical, PRIMARY)

        if series is None or not series.points:
            canvas.put(0, 2, "HISTORY", HEADING)
            canvas.put(2, 2, "No history data available.", SECONDARY)
            super().__init__(canvas, id="chart-panel")
            return

        hours = _span_hours(series)
        canvas.put(0, 2, f"TEMPERATURE — {series.label.upper()} — LAST {hours} HOURS", HEADING)

        samples = _resample(series.values, frame.plot_width)
        low, high = _bounds(samples)
        heights = [_eighths_for(frame, value, low, high) for value in samples]

        _paint_axis(canvas, frame, low, high, series.unit)
        _paint_area(canvas, frame, heights)
        _paint_time_ticks(canvas, frame, series)
        _paint_stats(canvas, frame, series)

        super().__init__(canvas, id="chart-panel")


def _paint_axis(canvas: Canvas, frame: ChartFrame, low: float, high: float, unit: str) -> None:
    for row in range(PLOT_TOP, frame.plot_bottom + 1):
        labelled = (frame.plot_bottom - row) % 2 == 0
        canvas.put(row, AXIS_COLUMN, "┤" if labelled else "│", AXIS)
        if labelled:
            # The area grows from the bottom edge of the lowest row, so a row's tick reads
            # the value at that edge: the bottom tick is exactly the low bound.
            value = low + (frame.plot_bottom - row) / frame.plot_rows * (high - low)
            canvas.put_right(row, AXIS_COLUMN - 1, f"{value:.0f}", ANNOTATION)
            for column in range(PLOT_LEFT + 9, frame.plot_right, 10):
                canvas.put(row, column, "·", GRID)
    canvas.put(frame.axis_row, AXIS_COLUMN, "└" + "─" * (frame.plot_right - AXIS_COLUMN), AXIS)
    canvas.put(PLOT_TOP - 1, 2, unit, ANNOTATION)


def _paint_area(canvas: Canvas, frame: ChartFrame, heights: list[int]) -> None:
    """Fill each column up to its height in eighths of a cell."""
    for index, eighths in enumerate(heights):
        column = PLOT_LEFT + index
        filled, remainder = divmod(eighths, SUB_ROWS)
        if remainder:
            crest_row, crest = frame.plot_bottom - filled, EIGHTH_BLOCKS[remainder - 1]
        else:
            # An exact number of cells: the topmost full block is itself the crest.
            crest_row, crest = frame.plot_bottom - filled + 1, FULL_BLOCK
            filled -= 1
        for offset in range(filled):
            canvas.put(frame.plot_bottom - offset, column, FULL_BLOCK, AREA_SHADE)
        canvas.put(crest_row, column, crest, PRIMARY)


def _paint_time_ticks(canvas: Canvas, frame: ChartFrame, series: HistorySeries) -> None:
    points = series.points
    for index in range(TIME_TICKS):
        position = index / (TIME_TICKS - 1)
        point = points[min(len(points) - 1, round(position * (len(points) - 1)))]
        column = PLOT_LEFT + round(position * (frame.plot_width - 1))
        label = point.at.strftime("%H:%M")
        left = min(max(column - len(label) // 2, PLOT_LEFT), frame.plot_right - len(label))
        canvas.put(frame.ticks_row, left, label, ANNOTATION)


def _paint_stats(canvas: Canvas, frame: ChartFrame, series: HistorySeries) -> None:
    unit = series.unit
    stats = (
        ("MIN", series.minimum),
        ("AVG", series.average),
        ("MAX", series.maximum),
        ("CURRENT", series.current),
    )
    column = 3
    for label, value in stats:
        canvas.put(frame.stats_row, column, label, SECONDARY)
        canvas.put(frame.stats_row, column + len(label) + 1, f"{value:.1f}{unit}", PRIMARY)
        column += STAT_SPACING


def _span_hours(series: HistorySeries) -> int:
    span = series.points[-1].at - series.points[0].at
    return max(1, round(span.total_seconds() / 3600))


def _resample(values: tuple[float, ...], width: int) -> list[float]:
    """Bucket-average the series into exactly `width` samples."""
    if not values:
        return []
    if len(values) <= width:
        return [
            values[round(index * (len(values) - 1) / max(1, width - 1))] for index in range(width)
        ]
    samples: list[float] = []
    for index in range(width):
        start = round(index * len(values) / width)
        end = max(start + 1, round((index + 1) * len(values) / width))
        bucket = values[start:end]
        samples.append(sum(bucket) / len(bucket))
    return samples


def _bounds(samples: list[float]) -> tuple[float, float]:
    low, high = min(samples), max(samples)
    if high == low:
        return low - 1.0, high + 1.0
    padding = (high - low) * 0.1
    return low - padding, high + padding


def _eighths_for(frame: ChartFrame, value: float, low: float, high: float) -> int:
    """Column height in eighths of a cell, at least one so every sample is visible."""
    fraction = (value - low) / (high - low)
    return max(1, round(fraction * frame.plot_rows * SUB_ROWS))
