.PHONY: interactive
interactive:
	uv run pole-attached-tray -- interactive

.PHONY: build
build:
	axe src/**/*.py -- uv run pole-attached-tray -- build

.PHONY: watch
watch:
	axe src/**/*.py -- uv run pole-attached-tray -- build --show

.PHONY: setup
setup:
	uv sync
	uv run pre-commit install
