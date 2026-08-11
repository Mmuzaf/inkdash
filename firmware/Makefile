ENV ?= inkplate10v2

# PlatformIO auto-detects the board. Only set this when more than one is connected;
# `pio device list` shows the candidates.
SERIAL_PORT ?=

UPLOAD_PORT_ARG = $(if $(SERIAL_PORT),--upload-port $(SERIAL_PORT))
MONITOR_PORT_ARG = $(if $(SERIAL_PORT),--port $(SERIAL_PORT))

.DEFAULT_GOAL := build


.PHONY: build
build: ## Compile the firmware
	pio run -e $(ENV)


.PHONY: flash
flash: ## Compile and upload over USB
	pio run -e $(ENV) -t upload $(UPLOAD_PORT_ARG)


.PHONY: monitor
monitor: ## Open the serial monitor
	pio device monitor $(MONITOR_PORT_ARG)


.PHONY: devices
devices: ## List connected serial devices
	pio device list


.PHONY: erase
erase: ## Erase the flash, clearing all saved settings
	pio run -e $(ENV) -t erase $(UPLOAD_PORT_ARG)


.PHONY: clean
clean: ## Remove build artifacts
	pio run -e $(ENV) -t clean
