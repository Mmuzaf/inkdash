from __future__ import annotations

from pathlib import Path

import pytest

from inkdash.config import Config
from inkdash.providers import MockProvider


async def test_mock_provider_is_deterministic(config: Config) -> None:
    provider = MockProvider(config.dashboard.mock_fixture)

    first = await provider.load()
    second = await provider.load()

    assert first == second


async def test_history_points_are_evenly_spaced(config: Config) -> None:
    model = await MockProvider(config.dashboard.mock_fixture).load()

    assert model.history is not None
    points = model.history.points
    assert len(points) == 48
    gaps = {(points[index + 1].at - points[index].at) for index in range(len(points) - 1)}
    assert len(gaps) == 1


async def test_a_missing_fixture_explains_itself(tmp_path: Path) -> None:
    provider = MockProvider(tmp_path / "absent.yaml")

    with pytest.raises(FileNotFoundError, match="dashboard.mock_fixture"):
        await provider.load()
