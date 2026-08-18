"""Home Assistant parsing, driven by recorded responses from a real instance."""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest

from inkdash.config import Config
from inkdash.providers import HomeAssistantProvider
from inkdash.providers.home_assistant import HomeAssistantError

HA_FIXTURES = Path(__file__).parent.parent / "fixtures" / "ha"

CONFIG_DATA: dict[str, Any] = {
    "home_assistant": {"url": "http://home-assistant.test:8123", "token": "test-token"},
    "entities": {
        "weather": {"entity": "weather.forecast_home"},
        "rooms": {
            "bedroom": {
                "temperature": "sensor.bedroom_temperature",
                "humidity": "sensor.bedroom_humidity",
            },
            "balcony": {
                "temperature": "sensor.balcony_temperature",
                "humidity": "sensor.balcony_humidity",
            },
        },
        "history": {"entity": "sensor.balcony_temperature", "label": "BALCONY", "hours": 24},
        "inkplate": {
            "battery": "sensor.inkplate_battery",
            "wifi": "sensor.inkplate_wifi_signal",
        },
    },
}


def _load(name: str) -> Any:
    return json.loads((HA_FIXTURES / name).read_text())


def _handler(missing: set[str] | None = None) -> Any:
    states = {state["entity_id"]: state for state in _load("states.json")}
    missing = missing or set()

    def handle(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/services/weather/get_forecasts":
            assert request.url.params.get("return_response") == "true"
            return httpx.Response(200, json=_load("get_forecasts.json"))
        if path.startswith("/api/history/period/"):
            return httpx.Response(200, json=_load("history_period.json"))
        if path.startswith("/api/states/"):
            entity_id = path.removeprefix("/api/states/")
            if entity_id in missing or entity_id not in states:
                return httpx.Response(404, json={"message": "Entity not found."})
            return httpx.Response(200, json=states[entity_id])
        if path == "/api/states":
            return httpx.Response(200, json=list(states.values()))
        return httpx.Response(404)

    return handle


@pytest.fixture
def provider(monkeypatch: pytest.MonkeyPatch) -> HomeAssistantProvider:
    return _provider(monkeypatch, _handler())


def _provider(
    monkeypatch: pytest.MonkeyPatch, handler: Any, config: Config | None = None
) -> HomeAssistantProvider:
    provider = HomeAssistantProvider(config or Config.model_validate(CONFIG_DATA))
    monkeypatch.setattr(
        provider,
        "_client",
        lambda: httpx.AsyncClient(
            base_url=provider.settings.url,
            transport=httpx.MockTransport(handler),
        ),
    )
    return provider


def test_a_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HA_TOKEN", raising=False)
    with pytest.raises(HomeAssistantError, match="HA_TOKEN"):
        HomeAssistantProvider(Config())


def test_the_url_falls_back_to_the_config_file() -> None:
    settings = Config.model_validate(CONFIG_DATA).home_assistant

    assert settings.resolve_url() == "http://home-assistant.test:8123"


def test_the_environment_overrides_the_configured_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HA_URL", "https://ha.example.com")
    settings = Config.model_validate(CONFIG_DATA).home_assistant

    assert settings.resolve_url() == "https://ha.example.com"


def test_an_empty_url_variable_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    """docker compose passes HA_URL through as an empty string when it is unset."""
    monkeypatch.setenv("HA_URL", "")
    settings = Config.model_validate(CONFIG_DATA).home_assistant

    assert settings.resolve_url() == "http://home-assistant.test:8123"


async def test_current_states_are_normalized(provider: HomeAssistantProvider) -> None:
    model = await provider.load()

    assert model.weather.condition == "cloudy"
    assert model.weather.temperature == pytest.approx(19.7)
    assert model.weather.entity_name == "Forecast Home"
    assert model.inkplate.battery_percent == 82
    assert model.inkplate.wifi_rssi_dbm == -55


async def test_the_wake_time_is_one_sleep_interval_from_the_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The panel fetches the image as it wakes, so rendering starts its next sleep."""
    config = Config.model_validate(CONFIG_DATA | {"dashboard": {"wakeup_every_seconds": 1800}})
    provider = _provider(monkeypatch, _handler(), config)

    model = await provider.load()

    assert model.inkplate.last_refresh == model.generated_at
    assert model.inkplate.next_wake == model.generated_at + timedelta(seconds=1800)


async def test_the_interval_the_device_reports_beats_the_configured_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the device knows what it sleeps for, so its own number wins."""
    config = Config.model_validate(
        CONFIG_DATA
        | {
            "dashboard": {"wakeup_every_seconds": 1800},
            "entities": CONFIG_DATA["entities"]
            | {
                "inkplate": {
                    "battery": "sensor.inkplate_battery",
                    "wifi": "sensor.inkplate_wifi_signal",
                    "wakeup_every_seconds": "number.inkplate_wakeup_every",
                }
            },
        }
    )
    provider = _provider(monkeypatch, _handler(), config)

    model = await provider.load()

    assert model.inkplate.next_wake == model.generated_at + timedelta(seconds=300)


async def test_a_device_that_has_not_reported_leaves_the_configured_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing number must not collapse the interval to zero."""
    config = Config.model_validate(
        CONFIG_DATA
        | {
            "dashboard": {"wakeup_every_seconds": 1800},
            "entities": CONFIG_DATA["entities"]
            | {"inkplate": {"wakeup_every_seconds": "number.inkplate_wakeup_every"}},
        }
    )
    provider = _provider(monkeypatch, _handler(missing={"number.inkplate_wakeup_every"}), config)

    model = await provider.load()

    assert model.inkplate.next_wake == model.generated_at + timedelta(seconds=1800)


async def test_sun_times_come_from_the_sun_entity(provider: HomeAssistantProvider) -> None:
    model = await provider.load()

    assert model.weather.sunrise is not None
    assert model.weather.sunset is not None
    assert model.weather.sunrise.hour == 3
    assert model.weather.sunset.hour == 18


async def test_forecast_uses_the_service_call(provider: HomeAssistantProvider) -> None:
    model = await provider.load()

    assert len(model.forecast) == 6, "forecast_days should cap the service response"
    assert model.forecast[0].day == "TUE"
    assert model.forecast[0].high == pytest.approx(22.6)
    assert model.forecast[0].low == pytest.approx(17.0)
    # Today's high and low are taken from the first forecast entry.
    assert model.weather.high == pytest.approx(22.6)


async def test_unavailable_states_become_none(provider: HomeAssistantProvider) -> None:
    model = await provider.load()

    balcony = model.room("balcony")
    assert balcony is not None
    assert balcony.temperature == pytest.approx(21.9)
    assert balcony.humidity is None


async def test_history_skips_non_numeric_states(provider: HomeAssistantProvider) -> None:
    model = await provider.load()

    assert model.history is not None
    assert model.history.label == "BALCONY"
    assert len(model.history.points) == 7, "the unavailable sample is dropped"
    assert model.history.minimum == pytest.approx(15.8)
    assert model.history.current == pytest.approx(21.9)


async def test_a_missing_entity_degrades_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _provider(monkeypatch, _handler(missing={"sensor.bedroom_temperature"}))

    model = await provider.load()

    bedroom = model.room("bedroom")
    assert bedroom is not None
    assert bedroom.temperature is None
    assert bedroom.humidity == pytest.approx(36)
    assert any("sensor.bedroom_temperature" in warning for warning in model.warnings)


async def test_probe_reports_entity_count(provider: HomeAssistantProvider) -> None:
    report = await provider.probe()

    assert report["entity_count"] == 9
