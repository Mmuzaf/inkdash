"""`.env` loading: the app reads it itself, but never over a real environment variable."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from inkdash.config import Config, DashboardConfig, load_env


@pytest.fixture(autouse=True)
def _fresh_loader() -> None:
    """The loader runs once per process, so each test needs it reset."""
    load_env.cache_clear()


def test_an_env_file_fills_an_unset_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("HA_URL=https://from-dotenv.test\nHA_TOKEN=file-token\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HA_URL", raising=False)
    monkeypatch.delenv("HA_TOKEN", raising=False)

    load_env()

    assert os.environ["HA_URL"] == "https://from-dotenv.test"
    assert os.environ["HA_TOKEN"] == "file-token"


def test_a_real_variable_wins_over_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("HA_URL=https://from-dotenv.test\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HA_URL", "https://from-the-shell.test")

    load_env()

    assert os.environ["HA_URL"] == "https://from-the-shell.test"


def test_the_file_is_found_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("HA_URL=https://from-the-root.test\n")
    nested = tmp_path / "deep" / "deeper"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    monkeypatch.delenv("HA_URL", raising=False)

    load_env()

    assert os.environ["HA_URL"] == "https://from-the-root.test"


def test_a_missing_env_file_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert load_env() is None


def test_loading_the_config_applies_the_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole point: no `source .env` step before running the CLI."""
    (tmp_path / ".env").write_text("HA_URL=https://config-load.test\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("HA_URL", raising=False)

    settings = Config.load().home_assistant

    assert settings.resolve_url() == "https://config-load.test"


def test_the_render_timings_fall_back_to_the_configuration() -> None:
    dashboard = DashboardConfig(render_interval_seconds=120.0, render_retry_seconds=7.0)

    assert dashboard.resolve_render_interval_seconds() == 120.0
    assert dashboard.resolve_render_retry_seconds() == 7.0


def test_the_environment_overrides_the_configured_render_timings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INKDASH_RENDER_INTERVAL_SECONDS", "45")
    monkeypatch.setenv("INKDASH_RENDER_RETRY_SECONDS", "9")
    dashboard = DashboardConfig(render_interval_seconds=120.0, render_retry_seconds=7.0)

    assert dashboard.resolve_render_interval_seconds() == 45.0
    assert dashboard.resolve_render_retry_seconds() == 9.0


def test_an_env_file_can_set_the_render_interval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("INKDASH_RENDER_INTERVAL_SECONDS=90\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("INKDASH_RENDER_INTERVAL_SECONDS", raising=False)

    assert Config.load().dashboard.resolve_render_interval_seconds() == 90.0


def test_an_unusable_render_interval_is_reported_rather_than_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Silently rendering on a number nobody chose is the worse failure."""
    monkeypatch.setenv("INKDASH_RENDER_INTERVAL_SECONDS", "every 5 minutes")

    with pytest.raises(ValueError, match="must be a number of seconds"):
        DashboardConfig().resolve_render_interval_seconds()


def test_a_render_interval_of_zero_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INKDASH_RENDER_INTERVAL_SECONDS", "0")

    with pytest.raises(ValueError, match="greater than zero"):
        DashboardConfig().resolve_render_interval_seconds()
