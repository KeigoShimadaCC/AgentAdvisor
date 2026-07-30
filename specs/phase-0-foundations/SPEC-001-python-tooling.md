---
id: SPEC-001
title: Python project tooling
phase: 0
status: verified
depends_on: []
parallel_with: [SPEC-002]
north_star_refs: ["5.8", "23"]
last_updated: 2026-07-31
---

# SPEC-001 — Python project tooling

## Summary

Bootstrap the Python project: dependency management, lint, typecheck, test, and a single quality-gate entry point. Everything later builds on these gates.

## Motivation

North star 5.8 (simple first) and 23 (transparent, testable system). No workflow code should exist before `make check` can prove it healthy.

## Scope

- `pyproject.toml` at repo root: project metadata, Python 3.12+, runtime deps `pydantic>=2`, `pyyaml`; dev deps `ruff`, `mypy`, `pytest`; ruff and mypy configuration in the same file.
- `uv` as the environment/dependency manager; committed `uv.lock`.
- Package `orchestrator/` (flat layout) with `__init__.py` exposing `__version__`.
- `tests/test_sanity.py`: imports the package, asserts version.
- `Makefile` with targets: `init` (uv sync), `lint`, `type`, `test`, `check` (lint + type + test).
- pytest marker registration for `live` and `live_slow`, deselected by default (`addopts = -m "not live and not live_slow"`), so model-calling tests never run accidentally.
- Remove `orchestrator/.gitkeep` and `tests/.gitkeep` as the folders gain content.

## Out of scope

CI pipelines, packaging/distribution, any workflow or schema code, pre-commit hooks.

## Design

Single root `pyproject.toml`, no src-layout (personal project, one package). mypy in strict-leaning mode (`disallow_untyped_defs = true` for `orchestrator/`). Ruff replaces both linter and formatter (`ruff check`, `ruff format --check` in `lint`), covering `orchestrator tests scripts`. Make targets run through `uv run`, with one deliberate exception: `smoke` calls bare `python3` because SPEC-002's script is stdlib-only by design and must run before `uv sync`.

## Deliverables

- [x] `pyproject.toml`, `uv.lock`
- [x] `orchestrator/__init__.py`
- [x] `tests/test_sanity.py`
- [x] `tests/test_markers.py` (dummy `live`-marked test proving default deselection)
- [x] `Makefile`

## Acceptance criteria

- [x] `make check` exits 0 from a clean clone after `make init`.
- [x] `uv run python -c "import orchestrator; print(orchestrator.__version__)"` prints a version.
- [x] `make lint`, `make type`, `make test` each run and exit 0 individually.
- [x] `uv run pytest` collects zero `live`/`live_slow` tests by default (marker registration verified with a dummy marked test).

## Verification plan

```
make init && make check
uv run python -c "import orchestrator; print(orchestrator.__version__)"
```

## Verification results

**2026-07-31 — PASS.** Environment: uv 0.10.0, resolved interpreter CPython 3.12.12, pytest 9.1.1.

- `make init && make check` → exit 0. Ruff: "All checks passed!" + "17 files already formatted"; mypy: "Success: no issues found"; pytest: `20 passed, 1 deselected`.
- `uv run python -c "import orchestrator; print(orchestrator.__version__)"` → `0.1.0`.
- `make lint`, `make type`, `make test` each exit 0 individually.
- `uv run pytest --collect-only -q` → `1/2 tests collected (1 deselected)`; `uv run pytest -m live --collect-only -q` → collects `tests/test_markers.py::test_live_marker_deselected_by_default`. Default deselection confirmed in both directions.

## Open questions

- None.
