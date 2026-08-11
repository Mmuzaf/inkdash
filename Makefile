SHELL := /bin/bash

.DEFAULT_GOAL := help

LAYOUT ?= home
OUTPUT_DIR ?= build
# See src/inkdash/cli.py for why this is not 8080. Override per deployment:
# make serve PORT=9000, or make docker-up PORT=9000.
PORT ?= 10825
HOST ?= 0.0.0.0

# Display geometry comes from the model named in config/config.yaml. WIDTH and HEIGHT only
# override the raster size of the PNG, for previewing on something other than the panel.
WIDTH ?=
HEIGHT ?=

SIZE_ARGS = $(if $(WIDTH),--width $(WIDTH)) $(if $(HEIGHT),--height $(HEIGHT))


.PHONY: help
help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make <target>\n\nTargets:\n"} \
		/^[a-zA-Z_0-9-]+:.*?##/ \
		{ printf "  %-20s %s\n", $$1, $$2 }' \
		$(MAKEFILE_LIST)


# ---------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------

.PHONY: bootstrap
bootstrap: ## Install Python and synchronize all dependencies
	uv python install
	uv sync --all-groups


.PHONY: sync
sync: ## Synchronize environment with uv.lock
	uv sync --all-groups


.PHONY: lock
lock: ## Resolve dependencies and update uv.lock
	uv lock


.PHONY: lock-check
lock-check: ## Verify that uv.lock is current
	uv lock --check


# ---------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------

.PHONY: preview
preview: ## Run interactive Textual dashboard
	uv run inkdash --layout $(LAYOUT) preview


.PHONY: preview-mock
preview-mock: ## Run dashboard using fixture data
	uv run inkdash --layout $(LAYOUT) --provider mock preview


.PHONY: model
model: ## Print normalized DashboardModel
	uv run inkdash --layout $(LAYOUT) dump-model


.PHONY: layouts
layouts: ## List available layouts
	uv run inkdash list-layouts


.PHONY: ha-check
ha-check: ## Verify Home Assistant connectivity and discover entity ids
	uv run inkdash ha-check


# ---------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------

.PHONY: render
render: render-png ## Default render target


.PHONY: render-svg
render-svg: ## Render dashboard to SVG
	uv run inkdash --layout $(LAYOUT) render \
		--format svg \
		--output $(OUTPUT_DIR)/dashboard.svg


.PHONY: render-png
render-png: ## Render dashboard to Inkplate PNG
	uv run inkdash --layout $(LAYOUT) render \
		--format png $(SIZE_ARGS) \
		--output $(OUTPUT_DIR)/dashboard.png


.PHONY: render-txt
render-txt: ## Render dashboard to plain text
	uv run inkdash --layout $(LAYOUT) render \
		--format txt \
		--output $(OUTPUT_DIR)/dashboard.txt


.PHONY: render-fixture
render-fixture: ## Render the fixture dashboard, never touching Home Assistant
	uv run inkdash --layout $(LAYOUT) --provider mock render \
		--format png $(SIZE_ARGS) \
		--output $(OUTPUT_DIR)/dashboard.png


.PHONY: validate-image
validate-image: render-fixture ## Validate Inkplate output constraints
	uv run python scripts/check_png.py $(OUTPUT_DIR)/dashboard.png


# ---------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------

.PHONY: format
format: ## Format source code
	uv run ruff format .


.PHONY: format-check
format-check: ## Verify formatting
	uv run ruff format --check .


.PHONY: lint
lint: ## Run Ruff
	uv run ruff check .


.PHONY: lint-fix
lint-fix: ## Fix lint violations where possible
	uv run ruff check --fix .


.PHONY: typecheck
typecheck: ## Run mypy
	uv run mypy src


.PHONY: test
test: ## Run tests
	uv run pytest


.PHONY: test-cov
test-cov: ## Run tests with coverage
	uv run pytest \
		--cov=inkdash \
		--cov-report=term-missing


.PHONY: snapshots
snapshots: ## Refresh golden snapshots
	UPDATE_SNAPSHOTS=1 uv run pytest tests/integration


.PHONY: check
check: lock-check format-check lint typecheck test validate-image ## Run every check CI runs
	@echo "All checks passed."


# ---------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------

.PHONY: serve
serve: ## Start renderer API locally
	uv run uvicorn \
		inkdash.server.api:app \
		--host $(HOST) \
		--port $(PORT) \
		--reload


# ---------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------

# The compose file lives in docker/ but describes the repository, so the project directory
# is pinned to the root. Without it Compose would treat docker/ as the project, resolve the
# build context and the config mount there, and skip the .env holding HA_TOKEN.
COMPOSE = docker compose --project-directory $(CURDIR) -f $(CURDIR)/docker/docker-compose.yml


.PHONY: docker-build
docker-build: ## Build renderer container
	$(COMPOSE) build


.PHONY: docker-up
docker-up: ## Start renderer services
	$(COMPOSE) up -d


.PHONY: docker-down
docker-down: ## Stop renderer services
	$(COMPOSE) down


.PHONY: docker-logs
docker-logs: ## Follow renderer logs
	$(COMPOSE) logs -f


# Where CasaOS pulls the image from. Override for a different account or registry:
# make docker-release IMAGE=someone/inkdash TAG=v1
IMAGE ?= mmuzaf/inkdash
TAG ?= latest

# Both architectures are built because the image is usually pushed from an arm64 Mac
# but runs on an amd64 Zimaboard; a plain docker build would publish arm64 only and
# CasaOS would refuse to start it. Multi-arch needs the docker-container driver, which
# the default builder does not use, hence the dedicated one.
BUILDX_BUILDER ?= inkdash-multiarch
PLATFORMS ?= linux/amd64,linux/arm64

.PHONY: docker-release
docker-release: ## Build and push a multi-arch image for CasaOS (needs docker login)
	docker buildx inspect $(BUILDX_BUILDER) >/dev/null 2>&1 || \
		docker buildx create --name $(BUILDX_BUILDER) --driver docker-container
	docker buildx build --builder $(BUILDX_BUILDER) --platform $(PLATFORMS) \
		-f $(CURDIR)/docker/Dockerfile -t $(IMAGE):$(TAG) --push $(CURDIR)


# ---------------------------------------------------------------------
# Firmware
# ---------------------------------------------------------------------

.PHONY: firmware-build
firmware-build: ## Build Inkplate firmware
	$(MAKE) -C firmware build


.PHONY: firmware-flash
firmware-flash: ## Flash Inkplate firmware via USB
	$(MAKE) -C firmware flash


.PHONY: firmware-monitor
firmware-monitor: ## Open serial monitor
	$(MAKE) -C firmware monitor


.PHONY: firmware-devices
firmware-devices: ## List connected serial devices
	$(MAKE) -C firmware devices


.PHONY: firmware-erase
firmware-erase: ## Erase the device, clearing all saved settings
	$(MAKE) -C firmware erase


.PHONY: firmware-clean
firmware-clean: ## Remove firmware build artifacts
	$(MAKE) -C firmware clean


# ---------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------

.PHONY: clean
clean: ## Remove generated artifacts
	rm -rf $(OUTPUT_DIR)
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache


.PHONY: clean-all
clean-all: clean ## Remove local Python environment as well
	rm -rf .venv
