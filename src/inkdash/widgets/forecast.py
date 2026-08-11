"""Multi-day forecast strip.

Each day is a column of day name, condition art, condition name, high and low. The art is
the same block the current-conditions panel draws, so today and the days after it read
alike, and the name below it says in words what the picture shows.
"""

from __future__ import annotations

from inkdash.model import ForecastDay
from inkdash.widgets.canvas import HEADING, PRIMARY, SECONDARY, Canvas
from inkdash.widgets.conditions import GLYPH_HEIGHT, GLYPH_WIDTH, glyph_for, label_for

GUTTER = 2
COLUMN_WIDTH = GLYPH_WIDTH + GUTTER

# Day name, the condition block, its caption, then high and low: what a caller has to leave
# free below the row it paints at.
STRIP_HEIGHT = GLYPH_HEIGHT + 4


def strip_width(days: int) -> int:
    """Cells needed for `days` columns, without a trailing gutter."""
    return days * COLUMN_WIDTH - GUTTER if days else 0


def paint_forecast(
    canvas: Canvas,
    row: int,
    column: int,
    days: tuple[ForecastDay, ...],
    *,
    max_days: int = 6,
) -> None:
    """Paint a day / condition / high / low column per day, starting at the given cell.

    The label and temperatures are centred on the block rather than aligned to its left
    edge, because the art carries the visual weight of the column.
    """
    for index, day in enumerate(days[:max_days]):
        left = column + index * COLUMN_WIDTH
        canvas.put_centered(row, left, GLYPH_WIDTH, day.day[:3], HEADING)
        for offset, line in enumerate(glyph_for(day.condition)):
            canvas.put(row + 1 + offset, left, line, SECONDARY)

        caption = row + GLYPH_HEIGHT + 1
        canvas.put_centered(caption, left, GLYPH_WIDTH, label_for(day.condition), SECONDARY)
        canvas.put_centered(caption + 1, left, GLYPH_WIDTH, _degrees(day.high), PRIMARY)
        canvas.put_centered(caption + 2, left, GLYPH_WIDTH, _degrees(day.low), SECONDARY)


def _degrees(value: float | None) -> str:
    return f"{value:.1f}" if value is not None else "--"
