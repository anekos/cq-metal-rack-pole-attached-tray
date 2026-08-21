.PHONY: watch
watch:
	axe src/**/*.py -- uv run pole-attached-tray -- build --show

.PHONY: build
build:
	axe src/**/*.py -- uv run pole-attached-tray -- build

.PHONY: setup
setup:
	uv sync
	uv run pre-commit install
