---
id: SPEC-016
title: Process Auditor role
phase: 3
status: draft
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-017]
north_star_refs: ["6.4", "8"]
last_updated: 2026-07-30
---

# SPEC-016 — Process Auditor role

## Summary

A cheap, constrained, read-only reviewer that checks relevance, duplication, and mandate compliance at defined checkpoints, and feeds the stop decision. It adds process control, never another opinion on the decision itself.

## Motivation

North star 6.4 and its decision-log entry: the Auditor protects against drift and waste; it must be inexpensive and heavily constrained.

## Scope

- `cursor/roles/auditor.md`: given the decision spec, current task graph, and recent artifacts, flag: tasks irrelevant to the decision question, duplicated work, artifacts violating their mandates (e.g. narrative essays instead of records), unsupported claims (assertions with no E-/A- reference), and a recommendation on the Stage 9 stop inputs (open critical gaps yes/no with reasons). Explicitly forbidden: proposing alternatives, re-arguing the thesis, adding research questions.
- `AuditFinding` artifact model: finding type enum, target IDs, severity, reason; plus the stop-input block consumed by SPEC-008's StopEvaluator.
- Read-only enforcement: invoked with the backend `read_only` flag (`--mode plan`); its only write is the output artifact, collected from stdout `result` and written by the orchestrator, not the agent (invocation-kit variant included here).
- Checkpoints (wired in SPEC-018): after planning, after each investigation wave, after challenge.
- `roles.yaml`: composer-2.5; projection: decision spec, task graph, artifact index with claims, budget snapshot.

## Out of scope

Stop-rule math (SPEC-008), citation verification against sources (SPEC-017), enforcement actions (orchestrator reacts to findings; reactions defined in SPEC-018).

## Design

Because plan mode cannot write files, the Auditor is the one role whose artifact is parsed from the JSON envelope `result` field (fenced YAML block) and validated orchestrator-side. If plan-mode output proves unreliable, fallback is a write-enabled invocation with a Write-permission profile: recorded as an open question resolved during implementation.

## Deliverables

- [ ] `cursor/roles/auditor.md`
- [ ] `AuditFinding` model + schema export
- [ ] Read-only invocation variant (stdout-artifact collection) in the invocation kit
- [ ] `roles.yaml` entry, projection config
- [ ] `tests/test_role_auditor.py` + fixtures (drifting task graph with a duplicate and an off-topic task); live mini-run test

## Acceptance criteria

- [ ] Fixture replay flags the planted duplicate and the off-topic task, and produces a valid stop-input block.
- [ ] Read-only variant: agent invocation runs in plan mode; the workspace contains no agent-written files; artifact parsed from stdout validates.
- [ ] Findings referencing nonexistent IDs fail validation.
- [ ] Live mini-run over the fixture graph returns a schema-valid AuditFinding set in ≤2 attempts.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_auditor.py -q
uv run pytest -m live -k auditor -q
```

## Verification results

—

## Open questions

- Reliability of fenced-YAML-in-stdout under plan mode; fallback path defined in Design if it fails.
