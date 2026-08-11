from __future__ import annotations

from datetime import datetime, timedelta

from inkdash.config import DisplayConfig
from inkdash.model import HistoryPoint, HistorySeries
from inkdash.widgets.base import Geometry
from inkdash.widgets.chart import EIGHTH_BLOCKS, FULL_BLOCK, PLOT_LEFT, ChartPanel

INKPLATE10 = Geometry.for_display(DisplayConfig())


def _chart(series: HistorySeries | None, geometry: Geometry = INKPLATE10) -> ChartPanel:
    return ChartPanel(geometry, series)


def _series(values: list[float]) -> HistorySeries:
    start = datetime(2026, 8, 10, 14, 0)
    return HistorySeries(
        label="BALCONY",
        points=tuple(
            HistoryPoint(at=start + timedelta(minutes=30 * index), value=value)
            for index, value in enumerate(values)
        ),
    )


def _lines(panel: ChartPanel) -> list[str]:
    return panel.painted_lines


def _column_heights(lines: list[str]) -> list[int]:
    """Rows containing a block glyph, per plot column."""
    blocks = set(EIGHTH_BLOCKS)
    return [
        sum(1 for line in lines if line[column] in blocks)
        for column in range(PLOT_LEFT, INKPLATE10.columns - 2)
    ]


def test_a_rising_series_fills_more_of_each_column() -> None:
    lines = _lines(_chart(_series([15.0, 18.0, 21.0, 24.0, 27.0])))

    assert "TEMPERATURE — BALCONY — LAST 2 HOURS" in "\n".join(lines)
    heights = _column_heights(lines)
    assert heights == sorted(heights), "a rising series must never fill a shorter column later"
    assert heights[0] < heights[-1]


def test_the_area_never_uses_the_dithered_shade_blocks() -> None:
    plot = "\n".join(_lines(_chart(_series([15.0, 22.0, 18.0, 30.0]))))

    assert not set(plot) & set("░▒▓"), "shaded blocks dither, which e-paper renders as mush"


def test_a_crest_resolves_values_finer_than_one_row() -> None:
    """Two samples inside the same row must still differ, which a row-per-value cannot do."""
    lines = _lines(_chart(_series([20.0, 20.0, 20.06, 20.12])))

    crests = {glyph for line in lines for glyph in line if glyph in EIGHTH_BLOCKS}
    assert len(crests) > 1, f"expected partial blocks at different heights, got {crests}"


def test_summary_reports_min_avg_max_and_current() -> None:
    lines = _lines(_chart(_series([15.0, 20.0, 25.0])))

    summary = next(line for line in lines if "MIN" in line)
    assert "MIN 15.0°C" in summary
    assert "AVG 20.0°C" in summary
    assert "MAX 25.0°C" in summary
    assert "CURRENT 25.0°C" in summary


def test_flat_series_does_not_divide_by_zero() -> None:
    lines = _lines(_chart(_series([20.0] * 10)))

    assert any(FULL_BLOCK in line for line in lines)


def test_missing_history_is_stated_plainly() -> None:
    lines = _lines(_chart(None))

    assert any("No history data available." in line for line in lines)


def test_panel_matches_the_dashboard_geometry() -> None:
    lines = _lines(_chart(_series([15.0, 20.0, 25.0])))

    assert len(lines) == 18
    assert {len(line) for line in lines} == {120}
