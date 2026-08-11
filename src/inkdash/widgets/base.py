"""Shared widget base and the fixed frame geometry of each supported display."""

from __future__ import annotations

from dataclasses import dataclass

from textual.widgets import Static

from inkdash.config import DisplayConfig
from inkdash.widgets.canvas import Canvas


@dataclass(frozen=True)
class Geometry:
    """Where each band of the dashboard sits, in character cells.

    The bands are laid out for one specific panel rather than reflowed to fit, so every
    number here is chosen, not derived. Supporting another Inkplate means adding an entry
    to :data:`LAYOUTS` and checking the result by eye.
    """

    columns: int
    rows: int
    divider_column: int
    panel_height: int
    chart_height: int
    header_height: int = 3

    @classmethod
    def for_display(cls, display: DisplayConfig) -> Geometry:
        try:
            return LAYOUTS[display.model]
        except KeyError:
            raise ValueError(
                f"No dashboard geometry for {display.model}. "
                f"Laid out so far: {', '.join(sorted(LAYOUTS))}"
            ) from None

    @property
    def left_region_width(self) -> int:
        return self.divider_column

    @property
    def right_region_width(self) -> int:
        return self.columns - self.divider_column

    @property
    def left_content_width(self) -> int:
        return self.left_region_width - 1

    @property
    def right_content_width(self) -> int:
        return self.right_region_width - 2

    @property
    def body_height(self) -> int:
        """Rows for a full-width body between the header and the closing rule."""
        return self.rows - self.header_height - 1


# Column 0 and 119 are the outer frame; column 80 divides the weather and sensor panels.
# The divider sits that far right because the forecast strip needs 76 cells to draw six
# condition blocks side by side, while the sensor table reads fine in the 40 left over.
LAYOUTS: dict[str, Geometry] = {
    "inkplate10": Geometry(
        columns=120,
        rows=42,
        divider_column=80,
        panel_height=19,
        chart_height=18,
    ),
}


class Panel(Static):
    """A Static that renders a pre-painted canvas at exactly the canvas size."""

    def __init__(self, canvas: Canvas, *, id: str | None = None) -> None:
        super().__init__(canvas.to_text(), id=id, markup=False)
        self._canvas = canvas
        self.styles.width = canvas.width
        self.styles.height = canvas.height

    @property
    def painted_lines(self) -> list[str]:
        """The rendered rows as plain strings, without styling. Useful in tests."""
        return str(self._canvas.to_text()).splitlines()


def format_temperature(value: float | None, unit: str = "°C") -> str:
    return f"{value:.1f}{unit}" if value is not None else f"--{unit}"


def format_percent(value: float | None) -> str:
    return f"{value:.0f}%" if value is not None else "--%"
