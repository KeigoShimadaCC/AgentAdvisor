.PHONY: init lint type test check smoke schemas

init:
	uv sync --group dev

lint:
	uv run ruff check orchestrator tests scripts
	uv run ruff format --check orchestrator tests scripts

type:
	uv run mypy orchestrator

test:
	uv run pytest

check: lint type test

smoke:
	python3 scripts/smoke_cursor_cli.py

schemas:
	uv run python3 -m orchestrator.artifacts.schema_export
