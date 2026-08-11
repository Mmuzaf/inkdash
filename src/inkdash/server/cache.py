"""Background renderer holding the most recent dashboard in memory.

The Inkplate wakes on battery, so everything between its request and the response is
radio-on time. Rendering inside the request would put the Home Assistant fan-out, a
headless Textual run and a rasterization on that path. Rendering on a timer instead makes
the request a dictionary lookup, and it decouples the panel from Home Assistant happening
to be reachable at the moment it wakes: a failed cycle keeps serving the last good
dashboard rather than an error.

A cold cache still renders on demand, so the first request after a restart is answered
rather than turned away. That is the only time a request waits for a render.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import blake2b

from inkdash.config import Config, DashboardConfig
from inkdash.controllers import DashboardController
from inkdash.layouts import list_layouts
from inkdash.model import DashboardModel
from inkdash.renderers import render_svg, render_text, svg_to_png, to_bytes

log = logging.getLogger(__name__)

MEDIA_TYPES = {
    "png": "image/png",
    "svg": "image/svg+xml",
    "txt": "text/plain; charset=utf-8",
}


@dataclass(frozen=True, slots=True)
class Form:
    """One rendering of a snapshot: the bytes, and the ETag that identifies them."""

    body: bytes
    etag: str
    media_type: str


@dataclass(frozen=True, slots=True)
class Snapshot:
    generated_at: str
    display: str
    forms: dict[str, Form]


class RenderCache:
    """Renders every layout on a timer and hands out the latest successful snapshot."""

    def __init__(self, load_config: Callable[[], Config] = Config.load) -> None:
        self._load_config = load_config
        self._snapshots: dict[str, Snapshot] = {}
        self._fingerprint: str | None = None
        defaults = DashboardConfig()
        self._interval_seconds = defaults.render_interval_seconds
        self._retry_seconds = defaults.render_retry_seconds
        self._lock = asyncio.Lock()

    def get(self, layout: str) -> Snapshot | None:
        return self._snapshots.get(layout)

    async def ensure(self, layout: str) -> Snapshot | None:
        """Return a snapshot, rendering one now if the cache is still cold."""
        snapshot = self.get(layout)
        if snapshot is not None:
            return snapshot

        async with self._lock:
            # Re-checked, because whoever held the lock has probably just filled the cache.
            if self.get(layout) is None:
                await self.refresh()
            return self.get(layout)

    @property
    def ready(self) -> bool:
        return bool(self._snapshots)

    @property
    def retry_after_seconds(self) -> int:
        """What to tell a client to wait, which is when this loop will next have tried."""
        return max(1, round(self._retry_seconds))

    async def refresh(self) -> bool:
        """Run one cycle. Returns whether it published a new generation."""
        config = self._load_config()
        self._interval_seconds = config.dashboard.resolve_render_interval_seconds()
        self._retry_seconds = config.dashboard.resolve_render_retry_seconds()

        model = await DashboardController(config).load()

        fingerprint = _fingerprint(model)
        if fingerprint == self._fingerprint:
            return False

        built = {layout: await _snapshot(model, config, layout) for layout in list_layouts()}
        self._snapshots = built
        self._fingerprint = fingerprint
        return True

    async def run(self) -> None:
        """Render forever. Started and cancelled by the server's lifespan hook."""
        while True:
            try:
                async with self._lock:
                    published = await self.refresh()
                log.info("Render cycle %s", "published" if published else "found no change")
                delay = self._interval_seconds
            except Exception:
                # Deliberately broad. Whatever broke, the dashboard already on the panel is
                # the best thing to keep serving, and the next cycle gets another attempt.
                log.exception("Render cycle failed, still serving the previous dashboard")
                delay = min(self._retry_seconds, self._interval_seconds)
            await asyncio.sleep(delay)


async def _snapshot(model: DashboardModel, config: Config, layout: str) -> Snapshot:
    """Render one model into every form."""
    svg = await render_svg(model, config, layout)
    bodies = {
        "svg": svg.encode(),
        "png": to_bytes(svg_to_png(svg, config.display.width, config.display.height)),
        "txt": (await render_text(model, config, layout)).encode(),
    }
    return Snapshot(
        generated_at=model.generated_at.isoformat(),
        display=config.display.model,
        forms={
            extension: Form(body=body, etag=_etag(body), media_type=MEDIA_TYPES[extension])
            for extension, body in bodies.items()
        },
    )


def _etag(body: bytes) -> str:
    return f'"{blake2b(body, digest_size=16).hexdigest()}"'


def _fingerprint(model: DashboardModel) -> str:
    """A hash of the model that changes whenever a render would change."""
    stable = model.model_dump_json(
        exclude={"generated_at": True, "inkplate": {"last_refresh", "next_wake"}}
    )
    return blake2b(stable.encode(), digest_size=16).hexdigest()
