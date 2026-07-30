---
id: SPEC-006
title: Role invocation kit
phase: 1
status: verified
depends_on: [SPEC-004, SPEC-005]
parallel_with: [SPEC-007, SPEC-008, SPEC-009]
north_star_refs: ["7.2", "11", "12", "13"]
last_updated: 2026-07-31
---

# SPEC-006 — Role invocation kit

## Summary

The complete primitive every stage uses: build an isolated agent workspace, project context into it, invoke the backend, validate the output artifact, and retry/escalate deterministically.

## Motivation

North star 7.2 (context projection), 12 (role-model mapping), 13 (escalation ladder). After this spec, "run the Challenger on this package" is one function call.

## Scope

- `orchestrator/roles_config.py`: role registry loaded from per-role config files `cursor/roles/<role>.yaml` (one file per role so Phase 3 specs stay file-disjoint): role md path, default model, escalation model, read_only flag, permission profile, projection include-list, output artifact type. Model-family helper (`family(model_id)`) for the Director≠Challenger check.
- `orchestrator/workspace.py`: builds a workspace under the out-of-repo runtime root (`<runtime_root>/<case-id>/<role>--<task-id>/`) containing the role md written as the workspace `AGENTS.md`, `inputs/*.yaml` (projected artifacts), `task.yaml` (assignment + required output filename + schema name), empty `outputs/`, and a generated `.cursor/cli.json` permission profile from the role config (Write limited to the workspace; Shell denied unless the role enables it, e.g. the Analyst). After the invocation the workspace is archived into `cases/<id>/agents/<role>--<task-id>/` via the case store and the runtime copy is deleted.
- `orchestrator/isolation.py`: `assert_isolated(workspace_path)` walks from the workspace up to the filesystem root and raises `WorkspaceNotIsolated` if any ancestor `AGENTS.md` exists. Called before every invocation. This enforces in code the empirical finding of `report-and-findings/2026-07-31-agents-md-leakage.md`: ancestor `AGENTS.md` files leak into agent instructions, a local file does not suppress them, and no CLI flag disables the behavior.
- `orchestrator/projection.py`: `project(case, include, budget_chars) -> list[artifact]`; include-list keys map to case-store queries via canonical `read_artifact`/`list_artifacts` paths (never ad-hoc `outputs/` guesses); unknown include keys raise `ProjectionError` listing valid keys; derived-summary keys (`task_graph`, `artifact_index`, `budget_snapshot`) produce compact YAML summaries; hard character budget with newest-first truncation and a truncation notice.
- `orchestrator/unpack.py`: batch artifacts (`EvidenceBatch`, `ObjectionBatch`) are transport envelopes, not blackboard state. `unpack_evidence_batch` / `unpack_objection_batch` allocate canonical IDs via `case.next_id`, write individual records to the blackboard, and audit the original-to-canonical ID mapping. `case.write_artifact` on a batch raises a targeted error pointing at the unpack functions.
- `orchestrator/invoke_role.py`: `invoke(case, role, task, *, backend=None, variant=None) -> Artifact`: workspace build → backend run → load and schema-validate `outputs/<required>.yaml` → on failure retry once same model with error feedback appended → escalate once to the role's escalation model → raise `RoleInvocationFailed`. Every attempt audited (model, usage, status). `variant` selects a named role config (`cursor/roles/<role>-<variant>.yaml`) for role variants like `director-framing`. `InvokeTask` carries a `mode: str | None` field written into `task.yaml` as a top-level `mode:` key, so roles can branch on task mode (provisional_thesis, preliminary_recommendation, repair, final_pass, post_planning, etc.).
- Invocation variants owned here, so role specs never modify the kit: (a) a cross-field validation hook registry per artifact type (e.g. citation-coverage rules, used by SPEC-014); (b) a read-only variant that runs `--mode plan` and collects the artifact from the JSON envelope `result` (fenced YAML) instead of a written file (used by SPEC-016).

## Out of scope

The actual role md contents (Phase 3), stage sequencing (SPEC-007/018), budget accounting beyond auditing attempts (SPEC-008 consumes the audit trail).

## Design

Prompt to the agent is minimal and fixed: read `task.yaml`, use `inputs/`, write the required output file, stop. All role-specific instruction lives in the projected `AGENTS.md`, all task-specific content in `task.yaml`, keeping invocations reproducible from the workspace alone. The workspace is the audit trail, so it is always preserved: the runtime copy is archived into the case before it is removed, and an invocation that fails validation is archived too (suffixed `--attempt-<n>`), never silently discarded. Validation reuses SPEC-003 models by name.

## Deliverables

- [x] `orchestrator/roles_config.py`, `orchestrator/workspace.py`, `orchestrator/projection.py`, `orchestrator/invoke_role.py`
- [x] `cursor/roles/<role>.yaml` skeletons for all roles (model mapping from the 2026-07-30 research report)
- [x] `tests/test_invocation.py` (StubBackend: happy path, invalid-output→retry→ok, retry→escalate→ok, escalate→fail)
- [x] Live mini-run test (`@pytest.mark.live`): trivial echo-role md writes a schema-valid artifact via composer-2.5

## Acceptance criteria

- [x] Workspace contains exactly AGENTS.md, task.yaml, inputs/, outputs/, and .cursor/cli.json and nothing else; role md content equals workspace AGENTS.md; the permission profile matches the role config.
- [x] Workspaces are created outside the repository tree, and `assert_isolated` raises when an ancestor `AGENTS.md` exists (unit test builds a polluted temp tree) and passes for a real workspace.
- [x] After invocation the workspace tree is archived under `cases/<id>/agents/<role>--<task-id>/` and the runtime copy is removed.
- [x] Projection respects the include-list (excluded artifact types never appear in inputs/) and the character budget.
- [x] Retry ladder behaves as specified in unit tests; every attempt appears in `audit.jsonl` with model and usage.
- [x] Read-only variant collects and validates a stdout artifact; cross-field validation hooks fire on registered artifact types (StubBackend unit tests).
- [x] Live mini-run yields a validated artifact in ≤2 attempts.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_invocation.py -q
uv run pytest -m live -k mini_run -q
```

## Verification results

**2026-07-31 — PASS.** `orchestrator/roles_config.py`, `orchestrator/isolation.py`, `orchestrator/projection.py`, `orchestrator/workspace.py`, and `orchestrator/invoke_role.py` are implemented with nine role configs in `cursor/roles/` and verified by `tests/test_invocation.py` (10 unit tests plus 1 live test). The retry ladder is deterministic as specified: attempt 1 on the role default model, attempt 2 on the same model with validation feedback appended to `task.yaml`, and attempt 3 on the escalation model before `RoleInvocationFailed`, with model, usage, status, and duration audited on every attempt.

Workspace and audit guarantees are enforced end to end: every attempt is archived, with successful runs under `cases/<id>/agents/<role>--<task-id>/` and failed attempts under `<role>--<task-id>--attempt-<n>`, so no failed invocation is silently discarded. Runtime workspaces are created under `runtime_root()/<case-id>/<role>--<task-id>/` outside the repository, `assert_isolated` walks to filesystem root and raises `WorkspaceNotIsolated` naming the offending path if any ancestor `AGENTS.md` exists, and generated `.cursor/cli.json` limits Read/Write to the workspace while denying `Shell(*)` unless explicitly enabled (Analyst only).

Role-to-model mapping is committed as: intake `composer-2.5`, planner `composer-2.5`, researcher `cursor-grok-4.5-low`, analyst `gpt-5.3-codex`, director `claude-opus-5-thinking-high`, challenger `gpt-5.6-sol-high`, auditor `composer-2.5`, synthesizer `claude-opus-5-thinking-high`, reviewer `composer-2.5`; Director and Challenger remain intentionally split across model families. Live mini-run verification passed with an echo role producing a schema-valid artifact via composer-2.5 on the first attempt, and the full gate (`make check`) is green.

## Open questions

- ~~Whether `--workspace <agent-dir>` should be passed in addition to `cwd`~~ **Resolved 2026-07-31: no.** The leakage experiment (E5 in `report-and-findings/2026-07-31-agents-md-leakage.md`) showed `--workspace` still inherits ancestor `AGENTS.md`, so it buys nothing that `cwd` does not already provide. Isolation comes from the out-of-repo runtime root plus `assert_isolated`, not from a flag.

## Phase 3 amendments (2026-07-31)

During Phase 3 implementation, three kit-level gaps were discovered and fixed:

1. **`variant` parameter.** `load_role_config(role, variant=None)` and `invoke(..., variant=None)` now support named role variants (`cursor/roles/<role>-<variant>.yaml`). SPEC-010's framing role (`director-framing.yaml`) uses this; without it, the variant config was unreachable from the invocation kit.

2. **`mode` field in `task.yaml`.** `WorkspaceTask` and `InvokeTask` carry a `mode: str | None` written into `task.yaml` as a top-level key. This lets roles branch on task mode without separate role md files: Director (provisional_thesis / preliminary_recommendation), Planner (repair), Challenger (final_pass), Auditor (post_planning / post_wave / post_challenge).

3. **Projection routed through canonical case-store paths.** The original `_output_artifact` fallback guessed `case.root / "outputs" / f"{key}.yaml"`, which was wrong for almost every artifact type (canonical storage is `shared/`, `shared/evidence/`, `analysis/`, etc.). Now every include key has a real handler using `case.read_artifact` / `case.list_artifacts`, and unknown keys raise `ProjectionError`. Derived-summary keys (`task_graph`, `artifact_index`, `budget_snapshot`) were added for the Auditor's projection needs. `PreliminaryRecommendation` and `FinalRecommendation` write paths were added to `case_store.py` (`shared/preliminary_recommendation.yaml` and `outputs/final_recommendation.yaml`).

4. **Batch unpacking.** `EvidenceBatch` and `ObjectionBatch` were added as transport-envelope models (see SPEC-012 and SPEC-015 amendments). `orchestrator/unpack.py` unpacks them into individual records with orchestrator-allocated IDs. `orchestrator/task_graph.py::_reconcile_success_unlocked` now dispatches batch artifacts to the unpackers instead of calling `write_artifact` directly.
