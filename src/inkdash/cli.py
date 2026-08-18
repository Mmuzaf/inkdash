"""Command line interface.

Developers normally reach these through the Makefile; the flags stay stable so the make
targets never need to change.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from inkdash import __version__
from inkdash.config import Config, load_env
from inkdash.controllers import DashboardController, build_provider
from inkdash.layouts import get_layout, list_layouts
from inkdash.model import DashboardModel
from inkdash.providers import HomeAssistantError, HomeAssistantProvider

# Not 8080, which is taken on any machine that also runs a self-hosting stack. The digits
# name the panel this serves: an Inkplate 10 that is 825 pixels tall. Staying below the
# ephemeral range keeps an outbound socket from claiming it first after a reboot.
DEFAULT_PORT = 10825

# Mirrors the SENSORS table in firmware/src/mqtt.cpp. Home Assistant builds an entity id
# out of the MQTT device name and the sensor name, and the device name is whatever was
# typed into the captive portal, so only the suffixes are known here.
INKPLATE_SENSORS = (
    "battery",
    "battery_voltage",
    "wifi_signal",
    "temperature",
    "boot_count",
    "boot_reason",
    "refresh_status",
)

# Nothing else publishes sensors with these names, so finding one identifies an Inkplate
# and recovers the prefix the rest of its sensors share.
INKPLATE_MARKERS = ("refresh_status", "boot_reason")

# The writable settings from the same table, which are not sensors.
INKPLATE_SETTINGS = (
    ("number", "wakeup_every"),
    ("text", "image_url"),
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="inkdash", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"inkdash {__version__}")
    parser.add_argument("-c", "--config", type=Path, help="Path to config.yaml")
    parser.add_argument("--provider", choices=("mock", "home_assistant"), help="Data source")
    parser.add_argument("--layout", help="Layout name")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("preview", help="Run the interactive Textual dashboard")
    subparsers.add_parser("list-layouts", help="List available layouts")
    subparsers.add_parser("dump-model", help="Print the normalized model as JSON")

    render = subparsers.add_parser("render", help="Render the dashboard to a file")
    render.add_argument("--format", choices=("png", "svg", "txt"), default="png")
    render.add_argument("--output", type=Path, required=True)
    render.add_argument("--width", type=int)
    render.add_argument("--height", type=int)

    check = subparsers.add_parser("ha-check", help="Verify Home Assistant and discover entities")
    check.add_argument("--dump-fixture", type=Path, help="Write raw states JSON for tests")

    serve = subparsers.add_parser("serve", help="Start the rendering API")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    serve.add_argument("--reload", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return _run(build_parser().parse_args(argv))
    except (HomeAssistantError, ValueError, FileNotFoundError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _run(args: argparse.Namespace) -> int:
    config = Config.load(args.config)
    if args.layout:
        get_layout(args.layout)

    if args.command == "list-layouts":
        print("\n".join(list_layouts()))
        return 0

    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "inkdash.server.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return 0

    if args.command == "ha-check":
        return asyncio.run(_ha_check(config, args.dump_fixture))

    model = asyncio.run(_load(config, args.provider, args.layout))

    if args.command == "dump-model":
        print(model.model_dump_json(indent=2))
        return 0

    if args.command == "preview":
        from inkdash.renderers import run_console

        run_console(model, config, args.layout)
        return 0

    if args.command == "render":
        return asyncio.run(_render(model, config, args))

    raise AssertionError(f"Unhandled command: {args.command}")


async def _load(config: Config, provider: str | None, layout: str | None) -> DashboardModel:
    controller = DashboardController(
        config,
        provider=build_provider(config, provider) if provider else None,
        layout=layout,
    )
    return await controller.load()


async def _render(model: DashboardModel, config: Config, args: argparse.Namespace) -> int:
    from inkdash.renderers import render_png, render_svg, render_text, to_bytes

    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "svg":
        output.write_text(await render_svg(model, config, args.layout))
    elif args.format == "txt":
        output.write_text(await render_text(model, config, args.layout))
    else:
        image = await render_png(model, config, args.layout, args.width, args.height)
        output.write_bytes(to_bytes(image))

    print(f"Wrote {output}")
    return 0


async def _ha_check(config: Config, dump_fixture: Path | None) -> int:
    env_file = load_env()
    print(f"Environment from {env_file}" if env_file else "No .env file found")

    provider = HomeAssistantProvider(config)
    try:
        report = await provider.probe()
    except Exception as error:  # noqa: BLE001 - the point is to report any failure clearly
        url = config.home_assistant.resolve_url()
        print(f"Home Assistant check FAILED for {url}: {error}")
        if "WRONG_VERSION_NUMBER" in str(error) and url.startswith("https://"):
            plain = url.replace("https://", "http://", 1)
            print(f"That port is serving plain HTTP, not TLS. Try {plain}")
        return 1

    states = report["states"]
    print(f"Connected to {report['url']} ({report['entity_count']} entities)")

    by_id = {str(state["entity_id"]): state for state in states}
    for entity in sorted(_configured_entities(config)):
        state = by_id.get(entity)
        status = "ok     " if state else "MISSING"
        print(f"  {status} {entity:<50} {_describe(state) if state else ''}".rstrip())

    _print_forecast(config, report)
    _print_inkplate(config, by_id)

    print("\nCandidate entities:")
    for entity_id, state in sorted(by_id.items()):
        if entity_id.startswith("weather.") or _looks_like_sensor(entity_id, state):
            print(f"  {entity_id:<50} {_describe(state)}")

    if dump_fixture:
        dump_fixture.parent.mkdir(parents=True, exist_ok=True)
        dump_fixture.write_text(json.dumps(states, indent=2))
        print(f"\nWrote {dump_fixture}")
    return 0


def _describe(state: dict[str, Any]) -> str:
    """One entity as `value unit  friendly name`, the same shape for every listing."""
    attributes = state.get("attributes")
    attributes = attributes if isinstance(attributes, dict) else {}
    value = f"{state['state']} {attributes.get('unit_of_measurement') or ''}".strip()
    return f"{value:<14} {attributes.get('friendly_name') or ''}".rstrip()


def _print_forecast(config: Config, report: dict[str, Any]) -> None:
    weather = config.entities.weather
    print(f"\nForecast for {weather.entity} ({weather.forecast_type}):")

    for warning in report.get("warnings", ()):
        print(f"  {warning}")

    forecast = report.get("forecast") or ()
    if not forecast:
        print("  no forecast returned")
        return

    for day in forecast:
        high = f"{day.high:.1f}" if day.high is not None else "--"
        low = f"{day.low:.1f}" if day.low is not None else "--"
        print(f"  {day.day:<4} {day.condition or '-':<14} high {high:>5}  low {low:>5}")


def _print_inkplate(config: Config, by_id: dict[str, dict[str, Any]]) -> None:
    """The panel's own sensors, which are what proves the firmware is reporting back.

    Most of these never reach the candidate listing: only battery, temperature and the
    signal strength carry a device class it recognises, so the boot and refresh
    diagnostics would otherwise be invisible here.
    """
    print("\nInkplate sensors, published by the firmware over MQTT:")

    prefixes = sorted(_inkplate_prefixes(by_id))
    if not prefixes:
        print("  none found, so the panel has not reported yet or has no broker set")
        print("  in the captive portal. firmware/SETUP.md covers the MQTT settings.")
        return

    for prefix in prefixes:
        for suffix in INKPLATE_SENSORS:
            entity_id = f"{prefix}{suffix}"
            state = by_id.get(entity_id)
            if state is not None:
                print(f"  {entity_id:<50} {_describe(state)}")

    slug = prefixes[0].removeprefix("sensor.")
    print("\nInkplate settings, changeable from Home Assistant (GUIDE.md):")
    for domain, suffix in INKPLATE_SETTINGS:
        entity_id = f"{domain}.{slug}{suffix}"
        state = by_id.get(entity_id)
        found = _describe(state) if state is not None else "not reported yet"
        print(f"  {entity_id:<50} {found}")

    # The status header shows "--" for whichever of these is not named in the config.
    inkplate = config.entities.inkplate
    suggestions = {
        "battery": f"sensor.{slug}battery",
        "wifi": f"sensor.{slug}wifi_signal",
        "wakeup_every_seconds": f"number.{slug}wakeup_every",
    }
    unset = {key: value for key, value in suggestions.items() if getattr(inkplate, key) is None}
    if not unset:
        return

    print("\n  To use them in the status header, add to config.yaml:")
    print("    entities:")
    print("      inkplate:")
    for key, value in unset.items():
        print(f"        {key}: {value}")


def _inkplate_prefixes(by_id: dict[str, dict[str, Any]]) -> set[str]:
    return {
        entity_id[: -len(marker)]
        for entity_id in by_id
        for marker in INKPLATE_MARKERS
        if entity_id.startswith("sensor.") and entity_id.endswith(f"_{marker}")
    }


def _configured_entities(config: Config) -> set[str]:
    entities = config.entities
    configured = {entities.weather.entity, entities.sun}
    for room in entities.rooms.values():
        configured.update(filter(None, (room.temperature, room.humidity)))
    configured.update(
        filter(None, (entities.history.entity, entities.inkplate.battery, entities.inkplate.wifi))
    )
    return {entity for entity in configured if entity}


def _looks_like_sensor(entity_id: str, state: dict[str, object]) -> bool:
    if not entity_id.startswith("sensor."):
        return False
    attributes = state.get("attributes")
    device_class = attributes.get("device_class") if isinstance(attributes, dict) else None
    return device_class in {"temperature", "humidity", "battery", "signal_strength"}


if __name__ == "__main__":
    sys.exit(main())
