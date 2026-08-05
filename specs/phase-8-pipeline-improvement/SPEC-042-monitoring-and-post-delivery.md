---
id: SPEC-042
title: Monitoring plan and post-delivery life
phase: 8
status: draft
depends_on: [SPEC-041]
parallel_with: [SPEC-043]
north_star_refs: ["3", "9", "16", "19"]
last_updated: 2026-08-04
---

# SPEC-042 — Monitoring plan and post-delivery life

## Summary

Turns the change-triggers, pre-mortem indicators and preventive actions the pipeline already
generates — and then discards at delivery — into a tracked monitoring plan: observables with
thresholds and check cadences, paired with a risk register of mitigations and owners, plus an
`advisor watch` surface that reports which checks are due. Closes the loop into the existing
outcome-recording and Brier calibration machinery.

## Motivation

Every case already produces the raw material of an indicators-and-warning set and a risk register,
and throws all of it away: `FailureMode.leading_indicators` and `FailureMode.preventive_action` on
each of up to five pre-mortem failure modes, and
`FinalRecommendation.recommendation_change_triggers`. All three are prose, all three are rendered
once, and no code ever reads them again. North star Section 3 item 10 promises "the conditions under which the
recommendation would change" and Section 19 wants forecasts retained so calibration can be computed;
without a tracking surface the first is decorative and the second depends on the user spontaneously
remembering to run `scripts/record_outcome.py`.

This is the change that converts a one-shot report into a standing position, which SPEC-025 already
argued is what separates a think tank from a one-off engagement.

## Scope

- `orchestrator/artifacts/monitoring.py`:
  - `IndicatorSource` — `premortem_failure_mode` | `change_trigger`.
  - `MonitoredIndicator` — `indicator_id` (`M-` prefixed), `source`, `source_ref`, `observable`,
    `threshold`, `check_cadence_days`, `would_imply`, `implicated_alternative`.
  - `TrackedMitigation` — `mitigation_id` (`R-` prefixed), `failure_mode`, `mitigation`,
    `owner`, `severity`, `status` (`not_started` | `in_place` | `not_applicable`),
    `triggered_by` (the `indicator_id`s whose breach makes this mitigation urgent).
  - `MonitoringPlan` — `case_id`, `delivered_at`, `indicators`, `mitigations`, `horizon`.
  - `IndicatorCheck` — `indicator_id`, `checked_at`, `observed`, `breached`, `note`.
- `orchestrator/monitoring.py` — deterministic assembly from the pre-mortem report and the final
  recommendation; `due_checks(plan, checks, as_of)` computing which indicators are overdue;
  `mitigations_for(plan, breached_indicator_ids)` returning the responses a breach makes urgent.
- `orchestrator/service/lexicon_data.yaml` — narration for `monitoring_plan_written`,
  `indicator_check_recorded` and `indicator_breached`.
- `cursor/roles/monitor.{md,yaml}` and `TaskRole.MONITOR` — one cheap invocation that converts each
  prose indicator into a concrete observable and threshold.
- `orchestrator/stages.py::handle_review` — assemble and write the plan after review passes, before
  the final approval gate.
- Monitoring store at `memory/monitoring/<case-id>.yaml`, alongside the existing memory root.
- `orchestrator/cli.py` — `advisor watch [--due] [--case-id]`, and
  `advisor check <case-id> <indicator-id> --observed <text> [--breached]`.
- `orchestrator/service/app.py` — a read endpoint for the plan and due checks.
- `frontend/src/screens/Delivery/` — a monitoring block listing indicators and any due checks.
- `scripts/record_outcome.py` — when a breach is recorded, prompt for outcome recording.
- `orchestrator/render.py` — a monitoring table replacing the bare trigger list.

## Out of scope

- **Making a case non-terminal.** See the design note; this is the central decision of the spec.
- Automated observation. Nothing fetches prices, filings or news. The user records observations.
- Scheduling, cron, notifications or email.
- Re-running any part of the pipeline automatically.

## Design

**The lifecycle decision: cases stay terminal.** The obvious design — a `MONITORING` stage the case
sits in indefinitely — is rejected. `orchestrator/state_machine.py` is built on one-way transitions
to terminal states, and the CLI, the supervisor, the service and the resume path all assume a case
runs to completion. Making a case non-terminal would ripple through every one of them for no gain in
decision quality.

Instead the monitoring plan is written **at delivery** and then lives **outside** the pipeline, in
the memory root that already outlives individual cases. `advisor watch` is a pure read over stored
plans and recorded checks. The case reaches `done` exactly as it does today.

**A breach does not reopen the case.** When an indicator breaches, `advisor watch` reports it and
recommends opening a **new linked case** seeded from the original — the existing `case_memory`
retrieval already gives a new case its predecessor's evidence and assumptions. A decision made under
different conditions is a different decision, and re-opening a delivered case would corrupt the
audit chain that is the product's main claim. The link is recorded as `supersedes` on the new case.

**Assembly is deterministic; only concretization is agent work.** `monitoring.py` collects every
`leading_indicators` entry across all failure modes plus every `recommendation_change_triggers`
entry, deduplicates them, and carries each one's provenance. The `monitor` role's only job is to
turn "competitor pricing pressure increases" into an observable with a threshold and a check
cadence. If that invocation fails, the plan is still written with the prose indicators and a flag
saying concretization did not run — a degraded plan beats no plan.

**Detection and response are two halves of the same artifact.** Indicators tell the user *what to
watch*; they do not say *what to do when it fires*. The pre-mortem already generates the other half
and the pipeline discards it: each `FailureMode` carries a `preventive_action` alongside its
`leading_indicators`, and that action reaches the rendered report as prose and is never tracked.
`TrackedMitigation` captures it with an owner and a status, linked by `triggered_by` to the
indicators drawn from the same failure mode, so a breach surfaces both the observation and the
response it was written for. Owner semantics match SPEC-041: free text, defaulting to the decision
owner. This is a register the user maintains, not one the system executes.

**Cadence.** `check_cadence_days` is bounded to `[7, 180]`. `due_checks` compares the last recorded
check per indicator against the cadence, with the delivery date as the origin.

## Deliverables

- [ ] `orchestrator/artifacts/monitoring.py` and `orchestrator/monitoring.py`
- [ ] `cursor/roles/monitor.{md,yaml}`, `TaskRole.MONITOR`, model table entries
- [ ] Plan assembly in `handle_review`, with the degraded path
- [ ] `TrackedMitigation` assembly from `FailureMode.preventive_action`, linked to indicators
- [ ] `memory/monitoring/` store with atomic writes
- [ ] `advisor watch` and `advisor check` commands
- [ ] Service read endpoint and Delivery-screen monitoring block
- [ ] `scripts/record_outcome.py` breach integration
- [ ] Renderer monitoring table and risk register
- [ ] Three `lexicon_data.yaml` narration entries
- [ ] `tests/test_monitoring.py`
- [ ] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [ ] `make check` and `make frontend-check` are green.
- [ ] Every `leading_indicators` entry and every `recommendation_change_triggers` entry from a
      fixture case appears in the assembled plan, asserted by count.
- [ ] `check_cadence_days` outside `[7, 180]` is rejected.
- [ ] `due_checks` unit tests cover: never checked, checked within cadence, checked beyond cadence,
      and an `as_of` before delivery.
- [ ] A failed `monitor` invocation still produces a plan, flagged as not concretized.
- [ ] A stub pipeline run reaches `done` and writes `memory/monitoring/<case-id>.yaml`.
- [ ] `advisor watch --due` lists exactly the overdue indicators for a seeded store.
- [ ] `advisor check` recording a breach prints the linked-case recommendation and does not mutate
      the delivered case directory.
- [ ] The delivered case's stage history is unchanged from the pre-change pipeline.
- [ ] Every `FailureMode.preventive_action` in a fixture case appears as a `TrackedMitigation`,
      asserted by count, each carrying an owner and a `triggered_by` list that resolves to
      indicators drawn from the same failure mode.
- [ ] `mitigations_for` returns exactly the mitigations linked to a breached indicator, and
      `advisor check --breached` prints them.
- [ ] `advisor report` renders a risk register with owner and status columns.
- [ ] No audit event emitted by this spec renders through the lexicon's unknown-event fallback,
      asserted by a test over `lexicon_data.yaml`.

## Verification plan

`make check`, `make frontend-check`, `uv run pytest tests/test_monitoring.py -v`, a stub pipeline run
followed by `advisor watch --due` against a store seeded with backdated checks, and a diff of the
case directory before and after `advisor check` to confirm immutability.

## Verification results

Not yet executed.

## Open questions

- Should the monitoring store be gitignored like `cases/` and `memory/`? Proposal: yes, it lives
  under the already-gitignored `memory/` root and is personal data.
