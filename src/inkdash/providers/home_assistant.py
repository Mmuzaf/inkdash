"""Home Assistant REST provider.

Authentication is bearer-token only: the REST API accepts nothing else. Every call is
individually fault tolerant, because a dashboard that renders without one sensor is far
more useful than one that renders nothing.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from inkdash.config import Config
from inkdash.model import (
    DashboardModel,
    ForecastDay,
    HistoryPoint,
    HistorySeries,
    InkplateState,
    RoomState,
    WeatherState,
)

UNAVAILABLE = {"unavailable", "unknown", "none", ""}


class HomeAssistantError(RuntimeError):
    pass


class HomeAssistantProvider:
    """Reads current states, the daily forecast and a history window from Home Assistant."""

    name = "home_assistant"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.settings = config.home_assistant
        token = self.settings.resolve_token()
        if not token:
            raise HomeAssistantError(
                f"No Home Assistant token. Set ${self.settings.token_env} to a long-lived "
                "access token created under your Home Assistant profile."
            )
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.resolve_url().rstrip("/"),
            headers=self._headers,
            timeout=self.settings.timeout_seconds,
            verify=self.settings.verify_ssl,
        )

    async def load(self) -> DashboardModel:
        entities = self.config.entities
        warnings: list[str] = []

        async with self._client() as client, asyncio.TaskGroup() as group:
            weather = group.create_task(self._state(client, entities.weather.entity, warnings))
            forecast = group.create_task(self._forecast(client, warnings))
            sun = group.create_task(self._state(client, entities.sun, warnings))
            rooms = group.create_task(self._rooms(client, warnings))
            battery = group.create_task(self._state(client, entities.inkplate.battery, warnings))
            rssi = group.create_task(self._state(client, entities.inkplate.wifi, warnings))
            history = group.create_task(self._history(client, warnings))

        # The panel asks for the image at the moment it wakes, so rendering time is the
        # start of its next sleep.
        now = datetime.now().astimezone()
        return DashboardModel(
            generated_at=now,
            weather=_weather_from(weather.result(), sun.result(), forecast.result()),
            forecast=forecast.result(),
            rooms=rooms.result(),
            inkplate=InkplateState(
                battery_percent=_as_int(battery.result()),
                wifi_rssi_dbm=_as_int(rssi.result()),
                last_refresh=now,
                next_wake=now + timedelta(minutes=self.config.dashboard.sleep_minutes),
            ),
            history=history.result(),
            warnings=tuple(warnings),
        )

    async def probe(self) -> dict[str, Any]:
        """Connectivity check plus entity discovery, used by `inkdash ha-check`.

        The forecast comes back normalized rather than raw, so the check shows the days the
        dashboard would actually draw. A forecast failure is a warning, not an error: the
        states call is what decides whether Home Assistant is reachable at all.
        """
        warnings: list[str] = []
        async with self._client() as client:
            response = await client.get("/api/states")
            response.raise_for_status()
            states: list[dict[str, Any]] = response.json()
            forecast = await self._forecast(client, warnings)
        return {
            "url": self.settings.resolve_url(),
            "entity_count": len(states),
            "states": states,
            "forecast": forecast,
            "warnings": tuple(warnings),
        }

    async def _state(
        self, client: httpx.AsyncClient, entity_id: str | None, warnings: list[str]
    ) -> dict[str, Any] | None:
        if not entity_id:
            return None
        try:
            response = await client.get(f"/api/states/{entity_id}")
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return payload
        except httpx.HTTPError as error:
            warnings.append(f"{entity_id}: {_reason(error)}")
            return None

    async def _rooms(self, client: httpx.AsyncClient, warnings: list[str]) -> tuple[RoomState, ...]:
        configured = self.config.entities.rooms
        results = await asyncio.gather(
            *(
                asyncio.gather(
                    self._state(client, room.temperature, warnings),
                    self._state(client, room.humidity, warnings),
                )
                for room in configured.values()
            )
        )
        return tuple(
            RoomState(
                name=name,
                temperature=_as_float(temperature),
                humidity=_as_float(humidity),
            )
            for name, (temperature, humidity) in zip(configured, results, strict=True)
        )

    async def _forecast(
        self, client: httpx.AsyncClient, warnings: list[str]
    ) -> tuple[ForecastDay, ...]:
        weather = self.config.entities.weather
        if not weather.entity:
            return ()
        try:
            # The forecast attribute was removed from weather entities, so it has to come
            # from a service call, and the service refuses to answer without return_response.
            response = await client.post(
                "/api/services/weather/get_forecasts",
                params={"return_response": "true"},
                json={"entity_id": weather.entity, "type": weather.forecast_type},
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
        except httpx.HTTPError as error:
            warnings.append(f"forecast: {_reason(error)}")
            return ()

        service_response = payload.get("service_response") or {}
        entries = (service_response.get(weather.entity) or {}).get("forecast") or []
        days: list[ForecastDay] = []
        for entry in entries[: weather.forecast_days]:
            when = _parse_datetime(entry.get("datetime"))
            days.append(
                ForecastDay(
                    day=when.strftime("%a").upper() if when else "---",
                    condition=entry.get("condition"),
                    high=_number(entry.get("temperature")),
                    low=_number(entry.get("templow")),
                )
            )
        return tuple(days)

    async def _history(
        self, client: httpx.AsyncClient, warnings: list[str]
    ) -> HistorySeries | None:
        history = self.config.entities.history
        if not history.entity:
            return None
        end = datetime.now(UTC)
        start = end - timedelta(hours=history.hours)
        try:
            response = await client.get(
                f"/api/history/period/{start.isoformat()}",
                params={
                    "filter_entity_id": history.entity,
                    "end_time": end.isoformat(),
                    "minimal_response": "",
                    "no_attributes": "",
                },
            )
            response.raise_for_status()
            payload: list[list[dict[str, Any]]] = response.json()
        except httpx.HTTPError as error:
            warnings.append(f"history: {_reason(error)}")
            return None

        points: list[HistoryPoint] = []
        for entry in payload[0] if payload else []:
            value = _number(entry.get("state"))
            when = _parse_datetime(entry.get("last_changed") or entry.get("last_updated"))
            if value is not None and when is not None:
                points.append(HistoryPoint(at=when, value=value))
        if not points:
            return None
        return HistorySeries(
            label=history.label or history.entity.split(".")[-1].replace("_", " ").upper(),
            points=tuple(points),
        )


def _weather_from(
    state: dict[str, Any] | None,
    sun: dict[str, Any] | None,
    forecast: tuple[ForecastDay, ...],
) -> WeatherState:
    attributes: dict[str, Any] = (state or {}).get("attributes", {})
    sun_attributes: dict[str, Any] = (sun or {}).get("attributes", {})
    today = forecast[0] if forecast else None
    return WeatherState(
        condition=_state_value(state),
        temperature=_number(attributes.get("temperature")),
        humidity=_number(attributes.get("humidity")),
        high=today.high if today else None,
        low=today.low if today else None,
        entity_name=attributes.get("friendly_name"),
        sunrise=_parse_datetime(sun_attributes.get("next_rising")),
        sunset=_parse_datetime(sun_attributes.get("next_setting")),
    )


def _state_value(state: dict[str, Any] | None) -> str | None:
    if not state:
        return None
    value = str(state.get("state", "")).strip()
    return None if value.casefold() in UNAVAILABLE else value


def _as_float(state: dict[str, Any] | None) -> float | None:
    return _number(_state_value(state))


def _as_int(state: dict[str, Any] | None) -> int | None:
    value = _as_float(state)
    return round(value) if value is not None else None


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _reason(error: httpx.HTTPError) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        return f"HTTP {error.response.status_code}"
    return type(error).__name__
