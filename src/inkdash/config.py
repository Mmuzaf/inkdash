"""What the user configures: the data sources, the entity ids and which display to use."""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from inkdash.display import DEFAULT_MODEL, DISPLAY_PROFILES, DisplayProfile

FONT_PATH = Path(__file__).parent / "assets" / "fonts" / "DejaVuSansMono.ttf"
FONT_BOLD_PATH = FONT_PATH.with_name("DejaVuSansMono-Bold.ttf")
FONT_FAMILY = "DejaVu Sans Mono"

ENV_FILE = ".env"


@cache
def load_env() -> str | None:
    """Read `.env` into the environment once per process, returning the file used, if any."""
    path = find_dotenv(ENV_FILE, usecwd=True)
    load_dotenv(path, override=False)
    return path or None


DEFAULT_CONFIG_PATHS = (
    Path("config/config.yaml"),
    Path("config/config.example.yaml"),
)


def _env_seconds(name: str, configured: float) -> float:
    """A positive number of seconds from the environment, or the configured value."""
    raw = os.environ.get(name)
    if not raw:
        return configured
    try:
        seconds = float(raw)
    except ValueError as error:
        raise ValueError(f"${name} must be a number of seconds, not {raw!r}") from error
    if seconds <= 0:
        raise ValueError(f"${name} must be greater than zero, not {seconds}")
    return seconds


class HomeAssistantConfig(BaseModel):
    """Connection settings for the Home Assistant REST API."""

    model_config = ConfigDict(frozen=True)

    url: str = "http://homeassistant.local:8123"
    url_env: str = "HA_URL"
    token_env: str = "HA_TOKEN"
    token: str | None = None
    timeout_seconds: float = 10.0
    verify_ssl: bool = True

    def resolve_url(self) -> str:
        """Return the base URL, preferring the environment variable."""
        return os.environ.get(self.url_env) or self.url

    def resolve_token(self) -> str | None:
        """Return the bearer token, preferring the environment variable."""
        return os.environ.get(self.token_env) or self.token


class RoomEntities(BaseModel):
    model_config = ConfigDict(frozen=True)

    temperature: str | None = None
    humidity: str | None = None


class WeatherEntities(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity: str = "weather.forecast_home"
    forecast_type: str = "daily"
    forecast_days: int = 6


class HistoryEntities(BaseModel):
    model_config = ConfigDict(frozen=True)

    entity: str | None = None
    label: str | None = None
    hours: int = 24


class InkplateEntities(BaseModel):
    model_config = ConfigDict(frozen=True)

    battery: str | None = None
    wifi: str | None = None
    # Overrides dashboard.wakeup_every_seconds when set.
    wakeup_every_seconds: str | None = None


class EntityMap(BaseModel):
    """Entity ids, kept out of layouts so a layout never knows about Home Assistant."""

    model_config = ConfigDict(frozen=True)

    weather: WeatherEntities = Field(default_factory=WeatherEntities)
    rooms: dict[str, RoomEntities] = Field(default_factory=dict)
    history: HistoryEntities = Field(default_factory=HistoryEntities)
    inkplate: InkplateEntities = Field(default_factory=InkplateEntities)
    sun: str = "sun.sun"


class DisplayConfig(BaseModel):
    """Which Inkplate the dashboard is rendered for. The model fixes size, grid and grays."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    model: str = DEFAULT_MODEL

    @field_validator("model")
    @classmethod
    def _known_model(cls, value: str) -> str:
        if value not in DISPLAY_PROFILES:
            known = ", ".join(sorted(DISPLAY_PROFILES))
            raise ValueError(f"Unknown display model {value!r}. Supported models: {known}")
        return value

    @property
    def profile(self) -> DisplayProfile:
        return DISPLAY_PROFILES[self.model]

    @property
    def width(self) -> int:
        return self.profile.width

    @property
    def height(self) -> int:
        return self.profile.height

    @property
    def columns(self) -> int:
        return self.profile.columns

    @property
    def rows(self) -> int:
        return self.profile.rows

    @property
    def grayscale_levels(self) -> int:
        return self.profile.grayscale_levels

    @property
    def cell_width(self) -> float:
        return self.width / self.columns

    @property
    def cell_height(self) -> float:
        return self.height / self.rows


class DashboardConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    layout: str = "home"
    title: str = "STATUS"
    provider: str = "mock"
    mock_fixture: Path = Path("tests/fixtures/home_dashboard.yaml")
    wakeup_every_seconds: int = Field(default=900, gt=0)
    render_interval_seconds: float = Field(default=5.0, gt=0)
    render_interval_env: str = "INKDASH_RENDER_INTERVAL_SECONDS"
    render_retry_seconds: float = Field(default=30.0, gt=0)
    render_retry_env: str = "INKDASH_RENDER_RETRY_SECONDS"

    def resolve_render_interval_seconds(self) -> float:
        """Seconds between background renders, preferring the environment variable."""
        return _env_seconds(self.render_interval_env, self.render_interval_seconds)

    def resolve_render_retry_seconds(self) -> float:
        """Seconds before retrying a failed render, preferring the environment variable."""
        return _env_seconds(self.render_retry_env, self.render_retry_seconds)


class Config(BaseModel):
    """Root configuration object."""

    model_config = ConfigDict(frozen=True)

    home_assistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    display: DisplayConfig = Field(default_factory=DisplayConfig)
    entities: EntityMap = Field(default_factory=EntityMap)

    @classmethod
    def load(cls, path: Path | None = None) -> Config:
        """Load configuration from YAML, falling back to the example then to defaults."""
        load_env()
        candidates = (path,) if path is not None else DEFAULT_CONFIG_PATHS
        for candidate in candidates:
            if candidate is not None and candidate.exists():
                raw: Any = yaml.safe_load(candidate.read_text()) or {}
                return cls.model_validate(raw)
        if path is not None:
            raise FileNotFoundError(f"Configuration file not found: {path}")
        return cls()
