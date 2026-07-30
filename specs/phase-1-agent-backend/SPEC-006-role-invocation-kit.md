---
id: SPEC-006
title: Role invocation kit
phase: 1
status: draft
depends_on: [SPEC-004, SPEC-005]
parallel_with: [SPEC-007, SPEC-008, SPEC-009]
north_star_refs: ["7.2", "11", "12", "13"]
last_updated: 2026-07-30
---

# SPEC-006 — Role invocation kit

## Summary

The complete primitive every stage uses: build an isolated agent workspace, project context into it, invoke the backend, validate the output artifact, and retry/escalate deterministically.

## Motivation

North star 7.2 (context projection), 12 (role-model mapping), 13 (escalation ladder). After this spec, "run the Challenger on this package" is one function call.

## Scope

- `orchestrator/roles_config.py`: role registry loaded from per-role config files `cursor/roles/<role>.yaml` (one file per role so Phase 3 specs stay file-disjoint): role md path, default model, escalation model, read_only flag, permission profile, projection include-list, output artifact type. Model-family helper (`family(model_id)`) for the Director≠Challenger check.
- `orchestrator/workspace.py`: builds `cases/<id>/agents/<role>--<task-id>/` containing the role md written as the workspace `AGENTS.md`, `inputs/*.yaml` (projected artifacts), `task.yaml` (assignment + required output filename + schema name), empty `outputs/`, and a generated `.cursor/cli.json` permission profile from the role config (Write limited to the workspace; Shell denied unless the role enables it, e.g. the Analyst).
- `orchestrator/projection.py`: `project(case, include, budget_chars) -> list[artifact]`; include-list keys map to case-store queries; hard character budget with newest-first truncation and a truncation notice.
- `orchestrator/invoke_role.py`: `invoke(case, role, task) -> Artifact`: workspace build → backend run → load and schema-validate `outputs/<required>.yaml` → on failure retry once same model with error feedback appended → escalate once to the role's escalation model → raise `RoleInvocationFailed`. Every attempt audited (model, usage, status).
- Invocation variants owned here, so role specs never modify the kit: (a) a cross-field validation hook registry per artifact type (e.g. citation-coverage rules, used by SPEC-014); (b) a read-only variant that runs `--mode plan` and collects the artifact from the JSON envelope `result` (fenced YAML) instead of a written file (used by SPEC-016).

## Out of scope

The actual role md contents (Phase 3), stage sequencing (SPEC-007/018), budget accounting beyond auditing attempts (SPEC-008 consumes the audit trail).

## Design

Prompt to the agent is minimal and fixed: read `task.yaml`, use `inputs/`, write the required output file, stop. All role-specific instruction lives in the projected `AGENTS.md`, all task-specific content in `task.yaml`, keeping invocations reproducible from the workspace alone. Workspaces are never deleted (they are the audit trail). Validation reuses SPEC-003 models by name.

## Deliverables

- [ ] `orchestrator/roles_config.py`, `orchestrator/workspace.py`, `orchestrator/projection.py`, `orchestrator/invoke_role.py`
- [ ] `cursor/roles/<role>.yaml` skeletons for all roles (model mapping from the 2026-07-30 research report)
- [ ] `tests/test_invocation.py` (StubBackend: happy path, invalid-output→retry→ok, retry→escalate→ok, escalate→fail)
- [ ] Live mini-run test (`@pytest.mark.live`): trivial echo-role md writes a schema-valid artifact via composer-2.5

## Acceptance criteria

- [ ] Workspace contains exactly AGENTS.md, task.yaml, inputs/, outputs/, and .cursor/cli.json and nothing else; role md content equals workspace AGENTS.md; the permission profile matches the role config.
- [ ] Projection respects the include-list (excluded artifact types never appear in inputs/) and the character budget.
- [ ] Retry ladder behaves as specified in unit tests; every attempt appears in `audit.jsonl` with model and usage.
- [ ] Read-only variant collects and validates a stdout artifact; cross-field validation hooks fire on registered artifact types (StubBackend unit tests).
- [ ] Live mini-run yields a validated artifact in ≤2 attempts.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_invocation.py -q
uv run pytest -m live -k mini_run -q
```

## Verification results

—

## Open questions

- Whether `--workspace <agent-dir>` should be passed in addition to `cwd` (depends on SPEC-002 leakage finding; decide at approval time based on smoke results).
