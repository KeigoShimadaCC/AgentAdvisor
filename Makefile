.PHONY: init lint type test check smoke smoke-droid schemas frontend-types frontend-check frontend-build frontend-install

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

smoke-droid:
	python3 scripts/smoke_droid_cli.py

schemas:
	uv run python3 -m orchestrator.artifacts.schema_export

frontend-install:
	cd frontend && npm install

frontend-types:
	cd frontend && npm install && npm run generate:types

frontend-check:
	cd frontend && npm run typecheck && npm run check:clean

frontend-build:
	cd frontend && npm install && npm run build
