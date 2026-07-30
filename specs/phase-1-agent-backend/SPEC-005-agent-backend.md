---
id: SPEC-005
title: AgentBackend interface and CursorCLIBackend
phase: 1
status: verified
depends_on: [SPEC-001, SPEC-003]
parallel_with: [SPEC-007, SPEC-008, SPEC-009]
north_star_refs: ["11", "5.4"]
last_updated: 2026-07-31
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

- [x] `orchestrator/backend.py`
- [x] `tests/test_backend.py` with a fake `cursor-agent` executable (shell script fixture) covering all five statuses
- [x] Live test `tests/test_backend_live.py` marked `@pytest.mark.live` (composer-2.5 echo, skipped by default)

## Acceptance criteria

- [x] Unit tests produce all five `RoleResult` statuses via the fake binary (success, timeout, nonzero exit, garbage stdout, `is_error` envelope).
- [x] Timeout reliably terminates the subprocess within timeout_s + 5s.
- [x] `uv run pytest -m live` passes on this machine (1 real invocation, model composer-2.5).
- [x] `make check` green (live tests excluded by default marker config).

## Verification plan

```
make check
uv run pytest tests/test_backend.py -q
uv run pytest -m live tests/test_backend_live.py -q
```

## Verification results

**2026-07-31 — PASS.** `orchestrator/backend.py` and the backend tests are complete, with `tests/test_backend.py` covering all five `RoleResult` statuses through a fake `cursor-agent` selected via injectable `binary_path`: `ok` (valid envelope), `agent_error` (`is_error: true`), `unparseable` (garbage stdout), `exit_error` (exit 17), and `timeout` (sleep past deadline). The timeout path uses `start_new_session=True` with `os.killpg(SIGKILL)`, and the timeout test asserts completion within `timeout_s + 5s` and verifies a spawned child process is gone, so hung invocations cannot wedge the orchestrator or leak orphans.

`--mode plan` is asserted to appear exactly when `read_only=True` and to be absent otherwise, and `raw_stdout`/`raw_stderr` are truncated to 8000 characters (4000 head + 4000 tail with a marker) to bound audit-log growth from runaway output. Live verification in `tests/test_backend_live.py` passed on composer-2.5 with status `ok`, session_id `8be0e238-e95d-4a02-95d9-550fe25c733c`, and usage `input_tokens=11987`, `output_tokens=40`, `cache_read_tokens=5957`; `make check` is green, and `uv run pytest -m live` collected 3 live tests with the 2 real-invocation tests passing against `cursor-agent 2026.07.23-e383d2b`.

Resolved ambiguity from the spec: truncation thresholds and unconditional `request_id`/`duration_ms` guarantees were not specified. The implementation now sets explicit truncation thresholds and handles `request_id`/`duration_ms` defensively as optional envelope fields with fallback behavior.

## Open questions

- None.
