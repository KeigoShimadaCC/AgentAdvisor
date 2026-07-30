---
id: SPEC-004
title: Case store and audit log
phase: 0
status: draft
depends_on: [SPEC-003]
parallel_with: []
north_star_refs: ["7", "7.3"]
last_updated: 2026-07-30
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
- `Case.write_artifact(model) / read_artifact(type, id)`: YAML via SPEC-003 models, atomic write (tmp file + `os.replace`), path derived from artifact type and ID.
- `Case.next_id(prefix) -> str`: monotonic per prefix (`E-`, `A-`, `T-`, `O-`), persisted in `shared/counters.yaml`, atomic.
- `Case.audit(event: AuditEvent)`: append-only JSONL, one line per event.
- `Case.list_artifacts(type)` for projections.

## Out of scope

State-machine semantics of `state.yaml` content (SPEC-007), any agent invocation, SQLite indexing (emergent work if files become limiting).

## Design

Plain functions and a small `Case` dataclass holding the root path; no global state. All writes atomic; audit strictly append (open in `a` mode, one `json.dumps` line, flush). Concurrent-safety scope for v1: single orchestrator process, multiple threads; `next_id` and audit guarded by a per-case `threading.Lock`. Cross-process locking is out of scope and documented as such.

## Deliverables

- [ ] `orchestrator/case_store.py`
- [ ] `tests/test_case_store.py`

## Acceptance criteria

- [ ] Creating two cases yields `case-001-*`, `case-002-*` with the full 7.3 layout.
- [ ] `write_artifact` is atomic: a simulated crash (exception injected between tmp write and replace) leaves no partial file at the final path.
- [ ] `next_id` never repeats across 100 threaded allocations per prefix.
- [ ] Audit events append in order and parse back into `AuditEvent` models.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_case_store.py -q
```

## Verification results

—

## Open questions

- None.
