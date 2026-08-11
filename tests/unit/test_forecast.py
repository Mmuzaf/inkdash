"""The forecast strip draws condition art, and stays inside the space it advertises."""

from __future__ import annotations

from inkdash.model import ForecastDay
from inkdash.widgets.canvas import Canvas
from inkdash.widgets.conditions import GLYPH_WIDTH, glyph_for
from inkdash.widgets.forecast import (
    COLUMN_WIDTH,
    GUTTER,
    STRIP_HEIGHT,
    paint_forecast,
    strip_width,
)

ART_ROWS = slice(1, 1 + len(glyph_for("sunny")))


def _lines(canvas: Canvas) -> list[str]:
    return str(canvas.to_text()).splitlines()


def _cells(canvas: Canvas, day: int) -> list[str]:
    """The cells one day's column owns, excluding its gutter."""
    left = day * COLUMN_WIDTH
    return [line[left : left + GLYPH_WIDTH] for line in _lines(canvas)]


def _day(condition: str) -> ForecastDay:
    return ForecastDay(day="TUE", condition=condition, high=22.6, low=17.0)


def test_each_day_is_a_column_of_label_art_and_temperatures() -> None:
    canvas = Canvas(strip_width(2), STRIP_HEIGHT)

    paint_forecast(canvas, 0, 0, (_day("rainy"), ForecastDay(day="WED", condition="sunny")))

    first = _cells(canvas, 0)
    assert first[0].strip() == "TUE"
    assert first[ART_ROWS] == list(glyph_for("rainy"))
    assert first[-3].strip() == "RAIN", "the caption sits between the art and the temperatures"
    assert first[-2].strip() == "22.6"
    assert first[-1].strip() == "17.0"

    second = _cells(canvas, 1)
    assert second[ART_ROWS] == list(glyph_for("sunny"))
    assert second[-3].strip() == "SUNNY"


def test_the_label_and_temperatures_are_centred_on_the_block() -> None:
    canvas = Canvas(strip_width(1), STRIP_HEIGHT)

    paint_forecast(canvas, 0, 0, (_day("cloudy"),))
    cells = _cells(canvas, 0)

    assert cells[0] == "    TUE    "
    assert cells[-2] == "   22.6    "


def test_an_unmapped_condition_is_captioned_with_what_arrived() -> None:
    canvas = Canvas(strip_width(1), STRIP_HEIGHT)

    paint_forecast(canvas, 0, 0, (_day("meteor-shower"),))

    assert _cells(canvas, 0)[-3].strip() == "METEOR-SHOW", "truncated, but still diagnosable"


def test_neighbouring_days_keep_their_gutter() -> None:
    canvas = Canvas(strip_width(2), STRIP_HEIGHT)

    paint_forecast(canvas, 0, 0, (_day("cloudy"), _day("cloudy")))

    for line in _lines(canvas):
        assert line[GLYPH_WIDTH : GLYPH_WIDTH + GUTTER].strip() == "", "art must not bleed across"


def test_conditions_are_told_apart() -> None:
    conditions = ("sunny", "cloudy", "partlycloudy", "rainy", "pouring", "snowy", "lightning")
    drawn = set()
    for condition in conditions:
        canvas = Canvas(strip_width(1), STRIP_HEIGHT)
        paint_forecast(canvas, 0, 0, (_day(condition),))
        drawn.add("\n".join(_cells(canvas, 0)[ART_ROWS]))

    assert len(drawn) == len(conditions), "every condition needs its own art"


def test_missing_temperatures_are_dashed() -> None:
    canvas = Canvas(strip_width(1), STRIP_HEIGHT)

    paint_forecast(canvas, 0, 0, (ForecastDay(day="TUE", condition="cloudy"),))
    cells = _cells(canvas, 0)

    assert cells[-2].strip() == "--"
    assert cells[-1].strip() == "--"


def test_only_the_days_that_fit_are_drawn() -> None:
    canvas = Canvas(strip_width(6), STRIP_HEIGHT)
    days = tuple(_day("cloudy") for _ in range(8))

    paint_forecast(canvas, 0, 0, days, max_days=6)

    assert _cells(canvas, 5)[ART_ROWS] == list(glyph_for("cloudy"))


def test_the_strip_stays_inside_the_height_it_advertises() -> None:
    """`STRIP_HEIGHT` is what callers reserve, so nothing may be painted past it."""
    canvas = Canvas(strip_width(1), STRIP_HEIGHT + 2)

    paint_forecast(canvas, 0, 0, (_day("cloudy"),))
    lines = _lines(canvas)

    assert lines[STRIP_HEIGHT - 1].strip() == "17.0"
    assert all(not line.strip() for line in lines[STRIP_HEIGHT:])
