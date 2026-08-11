from __future__ import annotations

from pathlib import Path

import pytest

from inkdash.config import Config
from inkdash.model import DashboardModel
from inkdash.providers import MockProvider

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOTS = Path(__file__).parent / "snapshots"


@pytest.fixture(autouse=True)
def _no_ambient_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a developer's own `.env` out of the suite.

    Set to empty rather than deleted: an empty variable counts as absent everywhere it is
    read, and `.env` loading leaves variables that are already present alone, so neither
    the developer's credentials nor their render timings can reach a test.
    """
    monkeypatch.setenv("HA_URL", "")
    monkeypatch.setenv("HA_TOKEN", "")
    monkeypatch.setenv("INKDASH_RENDER_INTERVAL_SECONDS", "")
    monkeypatch.setenv("INKDASH_RENDER_RETRY_SECONDS", "")


@pytest.fixture
def config() -> Config:
    return Config.model_validate(
        {"dashboard": {"mock_fixture": str(FIXTURES / "home_dashboard.yaml")}}
    )


@pytest.fixture
def model(config: Config) -> DashboardModel:
    return MockProvider(config.dashboard.mock_fixture).load_sync()
