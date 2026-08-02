.PHONY: init lint type test check smoke schemas frontend-types frontend-check

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

frontend-types:
	cd frontend && npm install && npm run generate:types

frontend-check:
	cd frontend && npm run check:clean && npx tsc --noEmit
