.PHONY: init lint type test check smoke smoke-droid schemas frontend-types frontend-check frontend-build frontend-install e2e-frontend e2e-frontend-install e2e-frontend-live

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
	cd frontend && npm run typecheck && npm run check:clean && npm run check:tokens && npm test

frontend-build:
	cd frontend && npm install && npm run build

e2e-frontend-install:
	cd frontend && npm install && npx playwright install --with-deps chromium webkit

# Each recipe line runs in its own shell, so every line needs its own `cd`:
# without it the three test lines ran from the repo root and could not find the
# config (SPEC-056).
e2e-frontend:
	cd frontend && npm install
	cd frontend && E2E_MODE=fixture npx playwright test --config=e2e/playwright.config.ts
	cd frontend && E2E_MODE=stub npx playwright test --config=e2e/playwright.config.ts
	cd frontend && E2E_MODE=replay npx playwright test --config=e2e/playwright.config.ts

# SPEC-037's opt-in live smoke. Spends real model usage: the spec skips itself
# unless both consent variables are set —
#   E2E_LIVE=1 AGENTADVISOR_E2E_BUDGET_ACK=1 make e2e-frontend-live
e2e-frontend-live:
	cd frontend && npm install
	cd frontend && E2E_MODE=live npx playwright test --config=e2e/playwright.config.ts
