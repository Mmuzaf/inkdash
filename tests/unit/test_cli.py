from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from inkdash.cli import main
from inkdash.model import ForecastDay
from inkdash.providers import HomeAssistantProvider

CONFIG = Path("config/config.example.yaml")


def test_list_layouts(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["list-layouts"]) == 0
    assert "home" in capsys.readouterr().out


def test_dump_model_emits_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-c", str(CONFIG), "--provider", "mock", "dump-model"]) == 0

    output = capsys.readouterr().out
    assert '"condition": "cloudy"' in output


def test_render_writes_the_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "nested" / "dashboard.txt"

    assert (
        main(
            [
                "-c",
                str(CONFIG),
                "--provider",
                "mock",
                "render",
                "--format",
                "txt",
                "--output",
                str(output),
            ]
        )
        == 0
    )
    assert "STATUS" in output.read_text()


def test_unknown_layout_fails_before_loading_data(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--layout", "nope", "list-layouts"]) == 1
    assert "Available layouts" in capsys.readouterr().err


def test_missing_config_is_reported(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["-c", "nowhere.yaml", "list-layouts"]) == 1
    assert "Configuration file not found" in capsys.readouterr().err


def test_missing_token_is_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "")

    assert main(["-c", str(CONFIG), "ha-check"]) == 1
    assert "HA_TOKEN" in capsys.readouterr().err


def test_ha_check_reports_values_and_the_forecast(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "token")
    report = {
        "url": "http://ha.test:8123",
        "entity_count": 2,
        "states": [
            {
                "entity_id": "sun.sun",
                "state": "above_horizon",
                "attributes": {"friendly_name": "Sun"},
            },
            {
                "entity_id": "sensor.bedroom_temperature",
                "state": "21.4",
                "attributes": {
                    "friendly_name": "Bedroom Temperature",
                    "unit_of_measurement": "°C",
                    "device_class": "temperature",
                },
            },
        ],
        "forecast": (ForecastDay(day="TUE", condition="rainy", high=25.9, low=20.4),),
        "warnings": (),
    }

    async def _probe(self: object) -> dict[str, object]:
        return report

    monkeypatch.setattr(HomeAssistantProvider, "probe", _probe)

    assert main(["-c", str(CONFIG), "ha-check"]) == 0

    lines = capsys.readouterr().out.splitlines()

    bedroom = next(line for line in lines if "sensor.bedroom_temperature" in line)
    assert bedroom.startswith("  ok ")
    assert "21.4 °C" in bedroom
    assert "Bedroom Temperature" in bedroom

    assert any(line.startswith("  MISSING sensor.kitchen_temperature") for line in lines)

    tuesday = next(line for line in lines if line.startswith("  TUE"))
    assert "rainy" in tuesday
    assert "high  25.9" in tuesday
    assert "low  20.4" in tuesday


def test_ha_check_says_so_when_no_forecast_comes_back(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "token")

    async def _probe(self: object) -> dict[str, object]:
        return {
            "url": "http://ha.test:8123",
            "entity_count": 0,
            "states": [],
            "forecast": (),
            "warnings": ("forecast: HTTP 500",),
        }

    monkeypatch.setattr(HomeAssistantProvider, "probe", _probe)

    assert main(["-c", str(CONFIG), "ha-check"]) == 0

    out = capsys.readouterr().out
    assert "forecast: HTTP 500" in out
    assert "no forecast returned" in out


def test_ha_check_lists_the_inkplate_sensors(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "token")

    async def _probe(self: object) -> dict[str, object]:
        return {
            "url": "http://ha.test:8123",
            "entity_count": 3,
            # The device was named "Hallway panel" in the captive portal, so the prefix
            # has to be recovered rather than assumed.
            "states": [
                {
                    "entity_id": "sensor.hallway_panel_refresh_status",
                    "state": "updated",
                    "attributes": {"friendly_name": "Hallway panel Refresh status"},
                },
                {
                    "entity_id": "sensor.hallway_panel_battery",
                    "state": "86",
                    "attributes": {
                        "friendly_name": "Hallway panel Battery",
                        "unit_of_measurement": "%",
                        "device_class": "battery",
                    },
                },
                {
                    "entity_id": "sensor.hallway_panel_boot_count",
                    "state": "12",
                    "attributes": {"friendly_name": "Hallway panel Boot count"},
                },
            ],
            "forecast": (),
            "warnings": (),
        }

    monkeypatch.setattr(HomeAssistantProvider, "probe", _probe)

    assert main(["-c", str(CONFIG), "ha-check"]) == 0

    out = capsys.readouterr().out
    assert "Inkplate sensors" in out

    # The boot and refresh diagnostics carry no device class, so this section is the
    # only place they appear.
    assert "sensor.hallway_panel_boot_count" in out
    assert "sensor.hallway_panel_refresh_status" in out

    # The example config already names an inkplate battery, so there is nothing to suggest.
    assert "add to config.yaml" not in out


def test_ha_check_suggests_the_inkplate_entities_when_unconfigured(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "token")
    config = tmp_path / "config.yaml"
    config.write_text("dashboard:\n  provider: home_assistant\n")

    async def _probe(self: object) -> dict[str, object]:
        return {
            "url": "http://ha.test:8123",
            "entity_count": 1,
            "states": [
                {
                    "entity_id": "sensor.hallway_panel_refresh_status",
                    "state": "updated",
                    "attributes": {"friendly_name": "Hallway panel Refresh status"},
                }
            ],
            "forecast": (),
            "warnings": (),
        }

    monkeypatch.setattr(HomeAssistantProvider, "probe", _probe)

    assert main(["-c", str(config), "ha-check"]) == 0

    out = capsys.readouterr().out
    assert "battery: sensor.hallway_panel_battery" in out
    assert "wifi: sensor.hallway_panel_wifi_signal" in out


def test_ha_check_says_so_when_no_inkplate_has_reported(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "token")

    async def _probe(self: object) -> dict[str, object]:
        return {
            "url": "http://ha.test:8123",
            "entity_count": 0,
            "states": [],
            "forecast": (),
            "warnings": (),
        }

    monkeypatch.setattr(HomeAssistantProvider, "probe", _probe)

    assert main(["-c", str(CONFIG), "ha-check"]) == 0

    out = capsys.readouterr().out
    assert "Inkplate sensors" in out
    assert "none found" in out


def test_a_tls_mismatch_suggests_plain_http(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HA_TOKEN", "token")
    monkeypatch.setenv("HA_URL", "https://ha.test:8123")

    async def _fail(self: object) -> None:
        raise httpx.ConnectError("[SSL: WRONG_VERSION_NUMBER] wrong version number")

    monkeypatch.setattr(HomeAssistantProvider, "probe", _fail)

    assert main(["-c", str(CONFIG), "ha-check"]) == 1
    assert "http://ha.test:8123" in capsys.readouterr().out
