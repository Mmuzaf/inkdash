"""What the Inkplate panels are: resolution, character grid and grayscale palette.

These are hardware facts rather than settings. A user picks a model by name in the config
file and never edits the numbers here, so nothing in this module depends on configuration
or on the dashboard being rendered.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

# The Inkplate 10 panel in 3-bit mode exposes exactly eight levels, 0-7.
INKPLATE_PALETTE: tuple[int, ...] = (0, 36, 73, 109, 146, 182, 219, 255)

PALETTE_HEX: tuple[str, ...] = tuple(
    f"#{level:02x}{level:02x}{level:02x}" for level in INKPLATE_PALETTE
)


class DisplayProfile(BaseModel):
    """Fixed panel specification for one Inkplate model.

    Every value is measured, not derived. A grid of 120 x 42 on the Inkplate 10 makes one
    character cell exactly 10 x 19.64 px.
    """

    model_config = ConfigDict(frozen=True)

    width: int
    height: int
    columns: int
    rows: int
    grayscale_levels: int = 8


DISPLAY_PROFILES: dict[str, DisplayProfile] = {
    "inkplate10": DisplayProfile(width=1200, height=825, columns=120, rows=42),
}

DEFAULT_MODEL = "inkplate10"
