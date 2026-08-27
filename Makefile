.PHONY: interactive
interactive:
	uv run app -- interactive

.PHONY: build
build:
	axe src/**/*.py -- uv run app -- build

.PHONY: watch
watch:
	axe src/**/*.py -- uv run app -- build --show

.PHONY: setup
setup:
	uv sync
	uv run pre-commit install
