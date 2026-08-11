FROM python:3.12-slim

# Pinned rather than :latest so an image rebuild cannot silently change the toolchain.
COPY --from=ghcr.io/astral-sh/uv:0.7.6 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies resolve in their own layer, so editing application code does not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY config ./config
COPY README.md ./
# The fixture ships too, so a container with no Home Assistant configured still renders.
COPY tests/fixtures/home_dashboard.yaml ./tests/fixtures/home_dashboard.yaml

RUN uv sync --locked --no-dev

EXPOSE 10825

# The bundled font is used with system fonts disabled, so no font packages are needed here.
CMD ["uv", "run", "--no-sync", "uvicorn", "inkdash.server.api:app", "--host", "0.0.0.0", "--port", "10825"]
