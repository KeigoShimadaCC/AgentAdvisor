---
id: SPEC-016
title: Process Auditor role
phase: 3
status: verified
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-017]
north_star_refs: ["6.4", "8"]
last_updated: 2026-07-31
---

# SPEC-016 — Process Auditor role

## Summary

A cheap, constrained, read-only reviewer that checks relevance, duplication, and mandate compliance at defined checkpoints, and feeds the stop decision. It adds process control, never another opinion on the decision itself.

## Motivation

North star 6.4 and its decision-log entry: the Auditor protects against drift and waste; it must be inexpensive and heavily constrained.

## Scope

- `cursor/roles/auditor.md`: given the decision spec, current task graph, and recent artifacts, flag: tasks irrelevant to the decision question, duplicated work, artifacts violating their mandates (e.g. narrative essays instead of records), unsupported claims (assertions with no E-/A- reference), and a recommendation on the Stage 9 stop inputs (open critical gaps yes/no with reasons). Explicitly forbidden: proposing alternatives, re-arguing the thesis, adding research questions.
- `AuditFinding` artifact model: finding type enum, target IDs, severity, reason, and a `high_stakes_escalation` flag (north star 13 reserves frontier-tier calls partly for cases the Auditor flags); plus the stop-input block consumed by SPEC-008's StopEvaluator.
- Read-only enforcement: invoked with the backend `read_only` flag (`--mode plan`); its only write is the output artifact, collected from stdout `result` and written by the orchestrator, not the agent (uses the SPEC-006 read-only stdout-collection variant).
- Checkpoints (wired in SPEC-018): after planning, after each investigation wave, after challenge.
- `cursor/roles/auditor.yaml`: composer-2.5; projection: decision spec, task graph, artifact index with claims, budget snapshot.

## Out of scope

Stop-rule math (SPEC-008), citation verification against sources (SPEC-017), enforcement actions (orchestrator reacts to findings; reactions defined in SPEC-018).

## Design

Because plan mode cannot write files, the Auditor is the one role whose artifact is parsed from the JSON envelope `result` field (fenced YAML block) and validated orchestrator-side. If plan-mode output proves unreliable, fallback is a write-enabled invocation with a Write-permission profile: recorded as an open question resolved during implementation.

## Deliverables

- [x] `cursor/roles/auditor.md`
- [x] `AuditFinding` model + schema export
- [x] Auditor wiring of the SPEC-006 read-only invocation variant
- [x] `cursor/roles/auditor.yaml`
- [x] `tests/test_role_auditor.py` + fixtures (drifting task graph with a duplicate and an off-topic task); live mini-run test

## Acceptance criteria

- [x] Fixture replay flags the planted duplicate and the off-topic task, and produces a valid stop-input block.
- [x] Read-only variant: agent invocation runs in plan mode; the workspace contains no agent-written files; artifact parsed from stdout validates.
- [x] Findings referencing nonexistent IDs fail validation.
- [x] Live mini-run over the fixture graph returns a schema-valid AuditFinding set in ≤2 attempts.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_auditor.py -q
uv run pytest -m live -k auditor -q
```

## Verification results

**2026-07-31 — PASS.** `cursor/roles/auditor.md` enforces the mandate (flag irrelevant tasks, duplicates, mandate violations, unsupported claims, produce stop-input block) with hard prohibitions (no proposing alternatives, no re-arguing the thesis, no adding research questions). The read-only variant (`invoke_read_only`) runs in plan mode and collects the artifact from stdout; the workspace stays clean (no agent-written files). The drift fixture contains a planted duplicate pair and an off-topic Kyoto vacation task, both flagged in replay. Findings referencing nonexistent IDs fail validation. The live mini-run passed in 1 attempt on `composer-2.5`, though the model did NOT fence the YAML in a code block and success depended on `_extract_yaml_block`'s fallback behavior. This confirms the spec's open question: fenced-YAML-in-stdout is not fully reliable under plan mode. The current parser fallback handles it; if stricter reliability is needed, the write-enabled fallback path documented in the Design section should be adopted.

## Open questions

- ~~Reliability of fenced-YAML-in-stdout under plan mode~~ **Resolved 2026-07-31.** The live run produced a schema-valid artifact in 1 attempt, but the model did NOT fence the YAML in a code block. Success depended on `_extract_yaml_block`'s fallback (returning the raw text when no fence is found). The fallback is sufficient for now; the write-enabled path remains available if parsing becomes unreliable with future model updates.
