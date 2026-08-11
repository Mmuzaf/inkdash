"""ASCII art for Home Assistant weather conditions.

The blocks follow wttr.in's weather icons, by way of `stormy`, because a rounded cloud drawn
with parentheses reads as a cloud at a glance where a single character does not. Weather
emoji are avoided even though the bundled DejaVu Sans Mono has them: at 10 px on e-paper a
filled pictograph turns into a grey smudge, while line art stays legible.

Every glyph is exactly :data:`GLYPH_WIDTH` by :data:`GLYPH_HEIGHT`, padded with blank rows
where the art is shorter, which is what lets a caller reserve space without measuring.
The keys are Home Assistant's own condition strings, so a state maps straight to a glyph.

Credit: https://github.com/chubin/wttr.in and https://github.com/ashish0kumar/stormy
"""

from __future__ import annotations

GLYPH_WIDTH = 11
GLYPH_HEIGHT = 5

Glyph = tuple[str, ...]

BLANK = " " * GLYPH_WIDTH
MISSING = "--"

GLYPHS: dict[str, Glyph] = {
    "sunny": (
        r"   \   /   ",
        r"    .-.    ",
        r" ― (   ) ― ",
        r"    `-'    ",
        r"   /   \   ",
    ),
    "clear-night": (
        BLANK,
        r"  *  .-.   ",
        r"    (   )  ",
        r"     `-'  *",
        BLANK,
    ),
    "partlycloudy": (
        r"  \  /     ",
        r'_ /"".-.   ',
        r"  \_(   ). ",
        r"  /(___(__)",
        BLANK,
    ),
    "cloudy": (
        BLANK,
        r"    .--.   ",
        r" .-(    ). ",
        r"(___.__)__)",
        BLANK,
    ),
    "fog": (
        BLANK,
        r"_ - _ - _ -",
        r" _ - _ - _ ",
        r"_ - _ - _ -",
        BLANK,
    ),
    "rainy": (
        r'_`/"".-.   ',
        r" ,\_(   ). ",
        r"  /(___(__)",
        r"    ' ' ' '",
        r"   ' ' ' ' ",
    ),
    "pouring": (
        r'_`/"".-.   ',
        r" ,\_(   ). ",
        r"  /(___(__)",
        r"  ‚'‚'‚'‚' ",
        r"  ‚'‚'‚'‚' ",
    ),
    "snowy": (
        r"    .-.    ",
        r"   (   ).  ",
        r"  (___(__) ",
        r"   *  *  * ",
        r"  *  *  *  ",
    ),
    "snowy-rainy": (
        r"    .-.    ",
        r"   (   ).  ",
        r"  (___(__) ",
        r"   * ' * ' ",
        r"  ' * ' *  ",
    ),
    "hail": (
        r"    .-.    ",
        r"   (   ).  ",
        r"  (___(__) ",
        r"   o  o  o ",
        r"  o  o  o  ",
    ),
    "lightning": (
        r"    .-.    ",
        r"   (   ).  ",
        r"  (___(__) ",
        r"   _/ _/   ",
        r"   /  /    ",
    ),
    "lightning-rainy": (
        r"    .-.    ",
        r"   (   ).  ",
        r"  (___(__) ",
        r"  _/ ' _/ '",
        r"   /  ' /  ",
    ),
    "windy": (
        BLANK,
        r"  ~~~~~,   ",
        r" ~~~~~~,   ",
        r"  ~~~~~,   ",
        BLANK,
    ),
    "windy-variant": (
        BLANK,
        r"  ~~~~~,   ",
        r" ~~~~~~,   ",
        r"  ~~~~~,   ",
        BLANK,
    ),
    "exceptional": (
        r"   .-.     ",
        r"    __)    ",
        r"   (       ",
        r"    `-'    ",
        r"     •     ",
    ),
}

UNKNOWN: Glyph = GLYPHS["exceptional"]

# Short names for captioning a glyph. Home Assistant's own strings are too long for a
# column this narrow - "partlycloudy" is 12 cells and "lightning-rainy" is 15 - and reading
# them as two words is easier anyway. Every label fits GLYPH_WIDTH.
LABELS: dict[str, str] = {
    "sunny": "SUNNY",
    "clear-night": "CLEAR",
    "partlycloudy": "PARTLY",
    "cloudy": "CLOUDY",
    "fog": "FOG",
    "rainy": "RAIN",
    "pouring": "HEAVY RAIN",
    "snowy": "SNOW",
    "snowy-rainy": "SLEET",
    "hail": "HAIL",
    "lightning": "STORM",
    "lightning-rainy": "STORM RAIN",
    "windy": "WINDY",
    "windy-variant": "WINDY",
    "exceptional": "UNUSUAL",
}


def glyph_for(condition: str | None) -> Glyph:
    return GLYPHS.get((condition or "").casefold(), UNKNOWN)


def label_for(condition: str | None) -> str:
    """Caption for a condition, falling back to whatever Home Assistant reported.

    An unmapped state is shown as-is rather than as "UNKNOWN", so a condition this code has
    not seen before is still diagnosable from the panel.
    """
    key = (condition or "").casefold()
    if not key:
        return MISSING
    return LABELS.get(key, key.upper()[:GLYPH_WIDTH])
