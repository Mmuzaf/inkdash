"""A fixed-size character grid with one palette shade per cell.

Widgets paint into a canvas rather than emitting markup, so a region is always exactly the
size it claims to be and every glyph carries a deliberate grayscale level.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.style import Style
from rich.text import Text

from inkdash.display import PALETTE_HEX

# Shade roles, following the palette hierarchy: 0 is black, 7 is the paper background.
PRIMARY = 0
HEADING = 1
SECONDARY = 2
AXIS = 3
ANNOTATION = 4
GRID = 5
INACTIVE = 6
BACKGROUND = 7


@dataclass(frozen=True)
class Border:
    """Box-drawing glyphs for one frame style.

    Keeping them together means a junction can never disagree with the edges it joins.
    """

    horizontal: str
    vertical: str
    top_left: str
    top_right: str
    bottom_left: str
    bottom_right: str
    tee_left: str
    tee_right: str
    tee_down: str
    tee_up: str
    # Tees where an inner single-line rule meets this frame's vertical edge.
    inner_left: str
    inner_right: str


SINGLE = Border(
    horizontal="─",
    vertical="│",
    top_left="┌",
    top_right="┐",
    bottom_left="└",
    bottom_right="┘",
    tee_left="├",
    tee_right="┤",
    tee_down="┬",
    tee_up="┴",
    inner_left="├",
    inner_right="┤",
)

DOUBLE = Border(
    horizontal="═",
    vertical="║",
    top_left="╔",
    top_right="╗",
    bottom_left="╚",
    bottom_right="╝",
    tee_left="╠",
    tee_right="╣",
    tee_down="╦",
    tee_up="╩",
    inner_left="╟",
    inner_right="╢",
)

# The style the dashboard is framed in. Inner tables stay single-line so they read as
# subdivisions of this frame rather than competing with it.
FRAME = DOUBLE


def ink(shade: int) -> str:
    """Hex colour for a palette level."""
    return PALETTE_HEX[shade]


class Canvas:
    """A width x height grid of characters, each with a palette shade."""

    def __init__(self, width: int, height: int, fill: str = " ") -> None:
        self.width = width
        self.height = height
        self._chars = [[fill] * width for _ in range(height)]
        self._shades = [[PRIMARY] * width for _ in range(height)]

    def put(self, row: int, column: int, text: str, shade: int = PRIMARY) -> None:
        """Write text starting at a cell, clipping at the canvas edge."""
        if not 0 <= row < self.height:
            return
        for offset, char in enumerate(text):
            position = column + offset
            if position < 0:
                continue
            if position >= self.width:
                break
            self._chars[row][position] = char
            self._shades[row][position] = shade

    def put_right(self, row: int, right: int, text: str, shade: int = PRIMARY) -> None:
        """Write text ending at the given column (exclusive)."""
        self.put(row, right - len(text), text, shade)

    def put_centered(
        self, row: int, left: int, width: int, text: str, shade: int = PRIMARY
    ) -> None:
        self.put(row, left + max(0, (width - len(text)) // 2), text, shade)

    def to_text(self) -> Text:
        """Collapse the grid into a Rich Text, merging runs that share a shade."""
        text = Text(no_wrap=True, overflow="crop")
        for row in range(self.height):
            if row:
                text.append("\n")
            chars = self._chars[row]
            shades = self._shades[row]
            start = 0
            for column in range(1, self.width + 1):
                if column == self.width or shades[column] != shades[start]:
                    text.append(
                        "".join(chars[start:column]),
                        Style(color=ink(shades[start])),
                    )
                    start = column
        return text
