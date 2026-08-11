"""HTTP rendering service.

A background task renders on a timer and this module hands out whatever it produced last,
so the panel's request costs a dictionary lookup and a socket write instead of a Home
Assistant fan-out and a rasterization. Only a cold cache renders inside the request, which
means the first caller after a restart is served rather than turned away.

Responses carry an ETag that only changes when the dashboard data does, so a device that
sends If-None-Match gets a 304 and can skip the two second e-paper refresh.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Header, Response
from fastapi.responses import JSONResponse, PlainTextResponse

from inkdash import __version__
from inkdash.layouts import list_layouts
from inkdash.server.cache import MEDIA_TYPES, RenderCache

log = logging.getLogger(__name__)

cache = RenderCache()


def _configure_logging() -> None:
    """Give the render loop somewhere to report, without turning on every library."""
    package_log = logging.getLogger("inkdash")
    if package_log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:     %(message)s"))
    package_log.addHandler(handler)
    package_log.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Start and stop the render loop around the server's own lifetime.

    A task needs a running event loop, which does not exist when this module is imported.
    This hook is the first point where it does, and the last point before requests arrive.
    """
    _configure_logging()
    task = asyncio.create_task(cache.run())
    try:
        yield
    finally:
        task.cancel()
        # Awaiting the cancellation lets a render in flight unwind at its next await, so
        # its Home Assistant client is closed rather than collected with open sockets.
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="inkdash", version=__version__, lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "version": __version__,
        "dashboard": "ready" if cache.ready else "rendering",
    }


@app.get("/layouts")
async def layouts() -> dict[str, list[str]]:
    return {"layouts": list_layouts()}


@app.get("/render/{layout}.{extension}")
async def render(
    layout: str,
    extension: str,
    if_none_match: str | None = Header(default=None),
) -> Response:
    if extension not in MEDIA_TYPES:
        return JSONResponse({"detail": f"Unsupported format: {extension}"}, status_code=404)

    if layout not in list_layouts():
        available = ", ".join(list_layouts())
        return JSONResponse(
            {"detail": f"Unknown layout: {layout!r}. Available layouts: {available}"},
            status_code=404,
        )

    try:
        snapshot = await cache.ensure(layout)
    except Exception:
        # Reached only by a cold cache whose first render failed, so there is nothing to
        # fall back to. Broad on purpose: a data source that will not answer should be a
        # 503 the panel retries, not a 500.
        log.exception("Rendering %s on demand failed", layout)
        snapshot = None

    if snapshot is None:
        return JSONResponse(
            {"detail": "No dashboard could be rendered yet"},
            status_code=503,
            headers={"Retry-After": str(cache.retry_after_seconds)},
        )

    form = snapshot.forms[extension]
    headers = {
        "ETag": form.etag,
        "Cache-Control": "no-cache",
        "X-Inkdash-Generated-At": snapshot.generated_at,
        "X-Inkdash-Layout": layout,
        "X-Inkdash-Display": snapshot.display,
        "X-Inkdash-Version": __version__,
    }
    if if_none_match == form.etag:
        return Response(status_code=304, headers=headers)

    if extension == "txt":
        return PlainTextResponse(form.body, headers=headers)
    return Response(form.body, media_type=form.media_type, headers=headers)
