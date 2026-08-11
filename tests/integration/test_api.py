from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from inkdash.config import Config
from inkdash.server import api
from inkdash.server.cache import RenderCache

FORMATS = ("png", "svg", "txt")


@pytest.fixture
def cache(config: Config) -> RenderCache:
    """Stands in for the module-level cache, left cold so requests warm it themselves."""
    return RenderCache(load_config=lambda: config)


@pytest.fixture
def client(cache: RenderCache) -> Iterator[TestClient]:
    original = api.cache
    api.cache = cache
    with TestClient(api.app) as test_client:
        yield test_client
    api.cache = original


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_reports_whether_a_dashboard_exists(config: Config) -> None:
    original = api.cache
    api.cache = RenderCache(load_config=lambda: config)
    try:
        # No lifespan, so nothing renders until a request asks for it.
        client = TestClient(api.app)
        assert client.get("/health").json()["dashboard"] == "rendering"
        client.get("/render/home.png")
        assert client.get("/health").json()["dashboard"] == "ready"
    finally:
        api.cache = original


def test_layouts_lists_the_registry(client: TestClient) -> None:
    response = client.get("/layouts")

    assert response.status_code == 200
    assert "home" in response.json()["layouts"]


def test_render_png_carries_inkplate_headers(client: TestClient) -> None:
    response = client.get("/render/home.png")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-inkdash-layout"] == "home"
    assert response.headers["x-inkdash-generated-at"].startswith("2026-08-11")
    assert response.headers["etag"]


def test_every_form_is_served_from_one_snapshot(client: TestClient) -> None:
    """Same data in three shapes: one timestamp between them, one ETag each."""
    stamps = set()
    etags = set()
    for extension in FORMATS:
        response = client.get(f"/render/home.{extension}")
        assert response.status_code == 200
        stamps.add(response.headers["x-inkdash-generated-at"])
        etags.add(response.headers["etag"])

    assert len(stamps) == 1
    assert len(etags) == len(FORMATS)


def test_unchanged_dashboard_answers_304(client: TestClient) -> None:
    first = client.get("/render/home.png")
    etag = first.headers["etag"]

    second = client.get("/render/home.png", headers={"If-None-Match": etag})

    assert second.status_code == 304
    assert second.content == b""


def test_a_cold_request_renders_and_a_second_one_does_not(
    client: TestClient, cache: RenderCache
) -> None:
    """The whole point of the background loop: only a cold cache costs a render."""
    client.get("/render/home.png")
    warmed = cache.get("home")
    assert warmed is not None

    response = client.get("/render/home.png")

    assert response.status_code == 200
    assert cache.get("home") is warmed
    assert response.content == warmed.forms["png"].body


def test_a_dashboard_that_cannot_be_rendered_is_a_503(config: Config) -> None:
    def load_config() -> Config:
        raise RuntimeError("Home Assistant is down")

    original = api.cache
    api.cache = RenderCache(load_config=load_config)
    try:
        response = TestClient(api.app).get("/render/home.png")
    finally:
        api.cache = original

    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"


def test_unknown_layout_is_a_404(client: TestClient) -> None:
    response = client.get("/render/nope.png")

    assert response.status_code == 404
    assert "Available layouts" in response.json()["detail"]


def test_unknown_format_is_a_404(client: TestClient) -> None:
    assert client.get("/render/home.jpeg").status_code == 404


def test_the_response_names_the_panel_it_was_rendered_for(client: TestClient) -> None:
    response = client.get("/render/home.txt")

    assert response.headers["x-inkdash-display"] == "inkplate10"
    lines = response.text.splitlines()
    assert len(lines) == 42
    assert {len(line) for line in lines} == {120}
