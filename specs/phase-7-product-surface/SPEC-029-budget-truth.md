---
id: SPEC-029
title: Budget truth and disclosed stops
phase: 7
status: verified
depends_on: [SPEC-028]
parallel_with: [SPEC-031]
north_star_refs: ["8", "13"]
last_updated: 2026-08-03
---

# SPEC-029 — Budget truth and disclosed stops

## Summary

Makes the budget system tell the truth. Today `budget_counters` in `state.yaml` is always `{}`
(the ledger binds to a `CaseState` instance that is never checkpointed), stage-level role
invocations consume no budget at all, `max_research_tasks` and `max_wall_clock_s` are dead
config, `Depth` maps to nothing, and consequently `INVESTIGATION_BUDGET_EXHAUSTED` and the
`DisclosureRecord` are unreachable in practice. The frontend's effort meters, the "Quick look /
Standard / Deep dive" choice, and the disclosed early-stop state (discovery report §13, C8) all
require these to be real.

## Motivation

North star Section 13: caps "are mandatory and enforced by the orchestrator"; Section 8 Stage 9:
"stopping because of budget or incomplete evidence must be disclosed in the final output." The
2026-07-31 evaluation run died on a real usage cap — exhaustion is a state users will hit.

## Scope

- `orchestrator/budget.py` + `orchestrator/pipeline.py` + `orchestrator/state_machine.py`:
  - One `CaseState` instance flows from `run()` through `run_case` (or the ledger is re-bound on
    each load) so `budget_counters` persists at every checkpoint. Regression test that inspects
    `state.yaml` mid-run.
  - `CaseState.started_at_run: datetime | None` — set on first transition of a `run()` call;
    total elapsed accumulates across resumes via a persisted `elapsed_s` counter updated at
    checkpoints.
- Consumption wiring:
  - every `invoke()` (stage-level roles included) consumes `agent_invocations` — the invocation
    kit accepts an optional ledger hook; `TaskGraph.dispatch` stops double-counting (its per-task
    consume is replaced by the same hook).
  - dispatching a `researcher` task additionally consumes `research_tasks`.
  - an attempt that runs on a role's escalation model consumes `high_tier_calls` when that
    model's `model_tier` is `high`.
  - wall clock: checked before each dispatch wave and in the stop evaluator against
    `max_wall_clock_s`.
- Depth mapping in `pipeline.run`: `light → SMALL_BUDGET`, `standard → DEFAULT_BUDGET`,
  `deep → DEEP_BUDGET` (new preset: 60 invocations / 3 concurrent / 2 repair / 25 research /
  10 high-tier / 3 h). An explicit `budget` argument still overrides; the effective profile name
  is audited at case start (`budget_profile_selected`).
- `StopEvaluatorInputs`: `deadline` fed from `decision_spec.deadline`, `depth_limit_reached`
  from the wall-clock/depth checks — both currently never set.
- Exhaustion behavior unchanged in shape (refused work stays `planned`, stage advances,
  `DisclosureRecord` written, renderer section appears) — but now reachable; integration test
  proves the full path.

## Out of scope

- Monetary cost tracking (explicitly out of scope since SPEC-008).
- Token-based budgets (audit usage remains the token record).
- UI rendering of effort (SPEC-035/036); CaseView derivation (SPEC-032).
- Retroactive repair of existing cases' empty counters.

## Design

The aliasing bug is fixed at the seam, not with a second ledger: `run_case` accepts the caller's
state object. Consumption hooks are injected, keeping `budget.py` free of invocation-kit imports.
`agent_invocations` counts successful *invocations* (one per `invoke()` call), not attempts —
the retry ladder stays an internal reliability mechanism; attempts remain visible per
`role_invocation_attempt` audit events. Double-counting is prevented by making the task runner's
consume and the stage-level consume the same code path.

## Deliverables

- [ ] persistence fix + `started_at_run`/`elapsed_s` on `CaseState`
- [ ] ledger hook in the invocation kit; task-graph consume unified
- [ ] `research_tasks`, `high_tier_calls`, wall-clock consumption wired
- [ ] `DEEP_BUDGET` preset + depth→profile mapping + `budget_profile_selected` audit event
- [ ] stop-evaluator deadline/depth inputs wired
- [ ] `tests/test_budget_truth.py` (persistence, double-count guard, exhaustion→disclosure e2e on
      stub backend, depth mapping, wall-clock stop with a monkeypatched clock)

## Acceptance criteria

- [ ] After a stub run halts at the framing gate, `state.yaml` shows non-zero
      `agent_invocations` equal to the count of `role_invocation_attempt` events with
      `attempt == 1` so far.
- [ ] A stub case with `max_agent_invocations=3` produces `task_budget_refused`, a
      `shared/disclosure_record.yaml` containing `investigation_budget_exhausted`, and a rendered
      report containing the "Budget/depth stop disclosure" section.
- [ ] `depth: deep` in the decision spec selects `DEEP_BUDGET` when no explicit budget is passed
      (unit test per depth value).
- [ ] With a monkeypatched clock past `max_wall_clock_s`, the stop decision fires with
      `user_deadline_or_depth_limit_reached` and the disclosure names the exhausted dimension.
- [ ] An escalation-model attempt on a high-tier role increments `high_tier_calls` exactly once.
- [ ] `make check` passes.

## Verification plan

```
uv run pytest tests/test_budget_truth.py tests/test_budget.py tests/test_pipeline_stub.py -q
make check
```

## Verification results

**2026-08-03 — verification plan executed.** `make check` green: ruff, ruff format, mypy on 65 source files, 639 unit tests (17 live deselected).

Spec's own plan run in full — 33 tests: `tests/test_budget_truth.py`, `tests/test_budget.py`, `tests/test_pipeline_stub.py`: all pass.

## Open questions

- None.
