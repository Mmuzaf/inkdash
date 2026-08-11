from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta

import pytest

from inkdash.config import Config
from inkdash.model import DashboardModel
from inkdash.server.cache import MEDIA_TYPES, RenderCache, _fingerprint


def _with_interval(config: Config, seconds: float) -> Config:
    dashboard = config.dashboard.model_copy(update={"render_interval_seconds": seconds})
    return config.model_copy(update={"dashboard": dashboard})


def test_the_fingerprint_ignores_the_clock(model: DashboardModel) -> None:
    """The regression that made the ETag useless: a new render stamped a new time."""
    later = model.model_copy(
        update={
            "generated_at": model.generated_at + timedelta(hours=1),
            "inkplate": model.inkplate.model_copy(
                update={
                    "last_refresh": model.generated_at + timedelta(hours=1),
                    "next_wake": model.generated_at + timedelta(hours=2),
                }
            ),
        }
    )

    assert _fingerprint(later) == _fingerprint(model)


def test_the_fingerprint_follows_the_data(model: DashboardModel) -> None:
    warmer = model.model_copy(
        update={"weather": model.weather.model_copy(update={"temperature": 99.0})}
    )

    assert _fingerprint(warmer) != _fingerprint(model)


async def test_a_snapshot_holds_every_form_of_one_load(config: Config) -> None:
    cache = RenderCache(load_config=lambda: config)

    assert not cache.ready
    assert await cache.refresh()

    snapshot = cache.get("home")
    assert snapshot is not None
    assert snapshot.display == "inkplate10"
    assert set(snapshot.forms) == set(MEDIA_TYPES)
    for extension, form in snapshot.forms.items():
        assert form.body
        assert form.etag
        assert form.media_type == MEDIA_TYPES[extension]


async def test_every_form_describes_the_same_instant(config: Config) -> None:
    """The reason the forms are grouped: one timestamp, one data load, three renderings."""
    cache = RenderCache(load_config=lambda: config)
    await cache.refresh()

    snapshot = cache.get("home")
    assert snapshot is not None
    assert snapshot.generated_at.startswith("2026-08-11")
    # The text form is the readable one, so the stamp it draws must be the one reported.
    assert "2026-08-11" in snapshot.forms["txt"].body.decode()
    # Different renderings of the same data, so distinct bytes and distinct ETags.
    assert len({form.etag for form in snapshot.forms.values()}) == len(snapshot.forms)


async def test_every_layout_is_rendered_by_one_cycle(config: Config) -> None:
    cache = RenderCache(load_config=lambda: config)
    await cache.refresh()

    assert cache.get("home") is not None
    assert cache.get("diagnostics") is not None


async def test_unchanged_data_keeps_the_previous_snapshot(config: Config) -> None:
    """Identity, not equality: an unchanged dashboard must not be re-rendered at all."""
    cache = RenderCache(load_config=lambda: config)
    await cache.refresh()
    first = cache.get("home")

    assert not await cache.refresh()
    assert cache.get("home") is first


async def test_a_cold_cache_renders_on_demand(config: Config) -> None:
    cache = RenderCache(load_config=lambda: config)

    snapshot = await cache.ensure("home")

    assert snapshot is not None
    assert cache.ready


async def test_a_warm_cache_is_not_re_rendered_on_request(config: Config) -> None:
    loads = 0

    def load_config() -> Config:
        nonlocal loads
        loads += 1
        return config

    cache = RenderCache(load_config=load_config)
    first = await cache.ensure("home")

    assert await cache.ensure("home") is first
    assert loads == 1


async def test_concurrent_cold_requests_render_once(config: Config) -> None:
    """Without the lock both callers would find an empty cache and each start a render."""
    loads = 0

    def load_config() -> Config:
        nonlocal loads
        loads += 1
        return config

    cache = RenderCache(load_config=load_config)
    first, second = await asyncio.gather(cache.ensure("home"), cache.ensure("home"))

    assert loads == 1
    assert first is second


async def test_a_failed_cycle_leaves_the_previous_dashboard_in_place(config: Config) -> None:
    broken = False

    def load_config() -> Config:
        if broken:
            raise RuntimeError("Home Assistant is down")
        return config

    cache = RenderCache(load_config=load_config)
    await cache.refresh()
    first = cache.get("home")

    broken = True
    with pytest.raises(RuntimeError):
        await cache.refresh()

    assert cache.get("home") is first


async def test_a_cold_cache_that_cannot_render_raises(config: Config) -> None:
    """The API turns this into a 503; there is no previous dashboard to fall back to."""

    def load_config() -> Config:
        raise RuntimeError("Home Assistant is down")

    cache = RenderCache(load_config=load_config)

    with pytest.raises(RuntimeError):
        await cache.ensure("home")
    assert not cache.ready


async def test_the_loop_survives_a_failing_cycle(config: Config) -> None:
    quick = _with_interval(config, 0.01)
    calls = 0

    def load_config() -> Config:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Home Assistant is down")
        return quick

    cache = RenderCache(load_config=load_config)
    task = asyncio.create_task(cache.run())
    try:
        async with asyncio.timeout(30):
            while calls < 3:
                await asyncio.sleep(0.01)
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    assert cache.get("home") is not None
