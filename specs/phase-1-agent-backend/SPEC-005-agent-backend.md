---
id: SPEC-005
title: AgentBackend interface and CursorCLIBackend
phase: 1
status: draft
depends_on: [SPEC-001, SPEC-003]
parallel_with: [SPEC-007, SPEC-008, SPEC-009]
north_star_refs: ["11", "5.4"]
last_updated: 2026-07-30
---

# SPEC-005 — AgentBackend interface and CursorCLIBackend

## Summary

The backend boundary: a typed interface for "run a role invocation, return a classified result", with the Cursor CLI as first implementation and a stub for tests.

## Motivation

North star Section 11: core workflow must never depend on Cursor specifics; a future direct-API backend must be addable without touching decision logic.

## Scope

`orchestrator/backend.py`:

- `RoleInvocation`: role, model, prompt, workspace path, timeout_s, read_only flag, env overrides.
- `RoleResult`: status enum (`ok`, `timeout`, `exit_error`, `unparseable`, `agent_error`), result_text, session_id, request_id, duration_ms, usage (tokens), raw_stdout/stderr (truncated), cli_version.
- `AgentBackend` protocol with `run(invocation) -> RoleResult`.
- `CursorCLIBackend`: builds `cursor-agent -p --trust --force --model <m> --output-format json <prompt>` (`--mode plan` when read_only), runs with `cwd=workspace` and hard `subprocess` timeout, parses the JSON envelope, maps failures to the status enum (validated pattern from `report-and-findings/2026-07-30-cursor-cli-research.md`).
- `StubBackend`: scripted results/side-effects for orchestrator tests.

## Out of scope

Workspace construction, context projection, output validation, retries/escalation (all SPEC-006); model-to-role mapping (config, SPEC-006); queueing.

## Design

Backend is stateless and knows nothing about cases, stages, or schemas; it transports prompts and classifies outcomes. Envelope parsing is defensive: nonzero exit → `exit_error`; JSON parse failure → `unparseable`; `is_error: true` → `agent_error`; timeout kills the process tree. CLI flags centralized in one function for easy version adaptation.

## Deliverables

- [ ] `orchestrator/backend.py`
- [ ] `tests/test_backend.py` with a fake `cursor-agent` executable (shell script fixture) covering all five statuses
- [ ] Live test `tests/test_backend_live.py` marked `@pytest.mark.live` (composer-2.5 echo, skipped by default)

## Acceptance criteria

- [ ] Unit tests produce all five `RoleResult` statuses via the fake binary (success, timeout, nonzero exit, garbage stdout, `is_error` envelope).
- [ ] Timeout reliably terminates the subprocess within timeout_s + 5s.
- [ ] `uv run pytest -m live` passes on this machine (1 real invocation, model composer-2.5).
- [ ] `make check` green (live tests excluded by default marker config).

## Verification plan

```
make check
uv run pytest tests/test_backend.py -q
uv run pytest -m live tests/test_backend_live.py -q
```

## Verification results

—

## Open questions

- None.
