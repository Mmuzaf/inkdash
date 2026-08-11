"""Condition art has to be a strict rectangle: callers reserve space without measuring it."""

from __future__ import annotations

import pytest

from inkdash.widgets.conditions import (
    GLYPH_HEIGHT,
    GLYPH_WIDTH,
    GLYPHS,
    UNKNOWN,
    glyph_for,
    label_for,
)

# What Home Assistant can put in a weather entity's state.
HA_CONDITIONS = (
    "clear-night",
    "cloudy",
    "exceptional",
    "fog",
    "hail",
    "lightning",
    "lightning-rainy",
    "partlycloudy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
    "sunny",
    "windy",
    "windy-variant",
)


@pytest.mark.parametrize("name", sorted(GLYPHS))
def test_every_glyph_is_exactly_one_block(name: str) -> None:
    glyph = GLYPHS[name]

    assert len(glyph) == GLYPH_HEIGHT
    for row in glyph:
        assert len(row) == GLYPH_WIDTH, f"{name}: {row!r} is {len(row)} cells"


@pytest.mark.parametrize("condition", HA_CONDITIONS)
def test_every_home_assistant_condition_has_art(condition: str) -> None:
    """`exceptional` shares the unknown block on purpose: unusual weather has no picture."""
    assert condition in GLYPHS


@pytest.mark.parametrize("condition", HA_CONDITIONS)
def test_every_condition_has_a_caption_that_fits_a_column(condition: str) -> None:
    label = label_for(condition)

    assert label
    assert len(label) <= GLYPH_WIDTH, f"{label!r} is wider than a forecast column"


def test_conditions_are_matched_regardless_of_case() -> None:
    assert glyph_for("Sunny") == GLYPHS["sunny"]
    assert label_for("Sunny") == "SUNNY"


def test_an_unmapped_condition_is_captioned_with_its_own_name() -> None:
    assert label_for("meteor-shower") == "METEOR-SHOW"
    assert len(label_for("meteor-shower")) == GLYPH_WIDTH


def test_a_missing_condition_is_dashed() -> None:
    assert label_for(None) == "--"
    assert label_for("") == "--"


def test_anything_unrecognized_is_drawn_as_unknown() -> None:
    assert glyph_for("meteor-shower") is UNKNOWN
    assert glyph_for(None) is UNKNOWN
