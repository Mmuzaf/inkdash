"""Validate that a rendered dashboard is displayable on the configured Inkplate.

Run through `make validate-image`, which is part of `make check`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

from inkdash.config import Config, DisplayConfig
from inkdash.display import INKPLATE_PALETTE


class ValidationError(RuntimeError):
    pass


def validate(path: Path, display: DisplayConfig) -> None:
    image = Image.open(path)
    width, height = display.width, display.height
    palette = INKPLATE_PALETTE[: display.grayscale_levels]

    if image.size != (width, height):
        raise ValidationError(f"Expected {width}x{height}, got {image.size[0]}x{image.size[1]}")

    if image.mode not in {"L", "P", "1"}:
        raise ValidationError(f"Expected a grayscale image, got mode {image.mode!r}")

    colors = image.convert("L").getcolors(maxcolors=256)
    if colors is None:
        raise ValidationError("Image contains more than 256 grayscale values")

    levels = sorted(value for _count, value in colors)
    if len(levels) > len(palette):
        raise ValidationError(
            f"Expected at most {len(palette)} grayscale values, got {len(levels)}"
        )

    unexpected = [level for level in levels if level not in palette]
    if unexpected:
        raise ValidationError(f"Levels outside the {display.model} palette: {unexpected}")

    print(f"{path}: {display.model} {width}x{height}, {len(levels)} grayscale levels {levels}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--config", type=Path, help="config file to read the display from")
    args = parser.parse_args(argv[1:])

    try:
        validate(args.path, Config.load(args.config).display)
    except (ValidationError, OSError, ValueError) as error:
        print(f"FAILED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
