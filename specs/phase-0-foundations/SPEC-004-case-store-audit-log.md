---
id: SPEC-004
title: Case store and audit log
phase: 0
status: verified
depends_on: [SPEC-003]
parallel_with: []
north_star_refs: ["7", "7.3"]
last_updated: 2026-07-31
---

# SPEC-004 — Case store and audit log

## Summary

The file-based blackboard: create/load case directories, write artifacts atomically, allocate IDs, and append audit events. The only module that touches `cases/` paths directly.

## Motivation

North star 7.3 fixes the case directory as the MVP blackboard; the audit log is what makes a finished case reconstructable (DoD C).

## Scope

`orchestrator/case_store.py`:

- `create_case(slug) -> Case`: allocates `cases/case-NNN-<slug>/` (NNN monotonic across `cases/`), builds the 7.3 layout: `shared/{decision_spec.yaml? (absent until framing), evidence/, assumptions/, objections/, task_graph.yaml}`, `agents/`, `analysis/`, `outputs/`, `state.yaml`, `audit.jsonl`.
- `load_case(case_id) -> Case`: validates layout, loads state.
- `Case.write_artifact(model) / read_artifact(type, id)`: YAML via SPEC-003 models, atomic write (tmp file + `os.replace`), path derived from artifact type and ID: `DecisionSpec → shared/decision_spec.yaml`, `EvidenceRecord → shared/evidence/E-nnn.yaml`, `AssumptionRecord → shared/assumptions/A-nnn.yaml`, `ObjectionRecord → shared/objections/O-nnn.yaml`, `TaskRecord → shared/tasks/T-nnn.yaml`. Individual `TaskRecord` files and `shared/task_graph.yaml` are separate concerns: the former are the typed task artifacts, the latter is the graph structure (edges, ordering, waves) owned by SPEC-009.
- `Case.next_id(prefix) -> str`: monotonic per prefix (`E-`, `A-`, `T-`, `O-`), persisted in `shared/counters.yaml`, atomic.
- `Case.audit(event: AuditEvent)`: append-only JSONL, one line per event.
- `Case.list_artifacts(type)` for projections.
- `Case.archive_agent_workspace(role, task_id, workspace_path)`: copies a finished runtime workspace into `agents/<role>--<task-id>/` for auditability, then the caller deletes the runtime copy.

**Runtime root separation (forced by the 2026-07-31 leakage finding).** `cases/` holds durable data only: artifacts, state, audit log, and archived workspace copies. Nothing is ever *executed* there. Live agent workspaces are created under a runtime root outside the repository (`AGENTADVISOR_RUNTIME_ROOT`, default `~/.local/share/agentadvisor/workspaces/`), because `cursor-agent` loads every `AGENTS.md` in its workspace's directory ancestry and would otherwise inherit this repo's development instructions. The case store owns the constant and exposes `runtime_root()`; SPEC-006 owns workspace construction and the isolation guard.

## Out of scope

State-machine semantics of `state.yaml` content (SPEC-007), any agent invocation, SQLite indexing (emergent work if files become limiting).

## Design

Plain functions and a small `Case` dataclass holding the root path; no global state. All writes atomic; audit strictly append (open in `a` mode, one `json.dumps` line, flush). Concurrent-safety scope for v1: single orchestrator process, multiple threads; `next_id` and audit guarded by a per-case `threading.Lock`. Cross-process locking is out of scope and documented as such.

## Deliverables

- [x] `orchestrator/case_store.py`
- [x] `tests/test_case_store.py`

## Acceptance criteria

- [x] Creating two cases yields `case-001-*`, `case-002-*` with the full 7.3 layout.
- [x] `write_artifact` is atomic: a simulated crash (exception injected between tmp write and replace) leaves no partial file at the final path.
- [x] `next_id` never repeats across 100 threaded allocations per prefix.
- [x] Audit events append in order and parse back into `AuditEvent` models.
- [x] `runtime_root()` resolves outside the repository tree and honours `AGENTADVISOR_RUNTIME_ROOT`; `archive_agent_workspace` reproduces a workspace's file tree under `agents/<role>--<task-id>/`.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_case_store.py -q
```

## Verification results

**2026-07-31 — PASS.** 7 tests in `tests/test_case_store.py`; `make check` exit 0 (31 passed suite-wide).

Covered: two-case allocation with full 7.3 layout and `shared/decision_spec.yaml` correctly absent; atomic write under an injected `os.replace` failure leaving neither a partial file nor a stray temp file; 100 concurrent `next_id` allocations per prefix yielding 100 unique monotonic IDs; audit append order and parse-back into `AuditEvent`; artifact write/read round-trip; `runtime_root()` resolving outside the repository tree and honouring `AGENTADVISOR_RUNTIME_ROOT`; `archive_agent_workspace` reproducing a nested workspace tree.

Review fix applied after implementation: `shared/tasks/` was created by `create_case` but missing from the layout validated by `load_case`, so a case missing that directory would have loaded successfully and then failed later on the first task write. It is now part of the required layout.

## Open questions

- None. Cross-process locking remains out of scope for v1 and is documented in the module docstring; revisit only if the orchestrator ever runs as more than one process.
