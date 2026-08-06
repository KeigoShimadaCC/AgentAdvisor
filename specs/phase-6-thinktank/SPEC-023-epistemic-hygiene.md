---
id: SPEC-023
title: Epistemic hygiene layer (assumption ledger, evidence critic, stage gates, reviewer verification)
phase: 6
status: verified
depends_on: [SPEC-018]
parallel_with: []
north_star_refs: ["6.4", "6.6", "6.8", "9", "11", "13", "17"]
last_updated: 2026-08-06
---

# SPEC-023 — Epistemic hygiene layer

## Summary

Closes the four quality holes the Phase 4 end-to-end evaluation exposed: zero assumption records
were produced in all five scenarios, evidence quality was the weakest rubric dimension (1.53/2.0)
because nothing scored source authority, the Auditor role was defined but effectively never
invoked and had no enforcement power, and the Reviewer passed every case on the first attempt
without performing any verifiable check. This spec makes the deliberation process police itself
with deterministic machinery plus two cheap agent passes.

## Motivation

North star Section 6.4 requires assumptions to be first-class tracked objects, 6.6 gives the
Process Auditor authority over process integrity, 6.8 requires the calibration/citation reviewer
to actually verify citations, and Section 11 requires provenance discipline. The Phase 4 findings
in `specs/ROADMAP.md` show all four are currently aspirational rather than enforced.

## Scope

**Assumption ledger**

- `orchestrator/artifacts/assumptions.py`: add `AssumptionBatch` (cap 10, explicit
  `no_assumptions_found` outcome), mirroring `EvidenceBatch`.
- `orchestrator/unpack.py`: `unpack_assumption_batch` minting canonical `A-` IDs.
- New role `assumption_analyst` (`cursor/roles/assumption_analyst.{md,yaml}`) and
  `TaskRole.ASSUMPTION_ANALYST`.
- New stage `CaseStage.ASSUMPTION_LEDGER` between `INVESTIGATION` and
  `PRELIMINARY_RECOMMENDATION`.

**Evidence critic (deterministic)**

- `orchestrator/artifacts/evidence_critique.py`: `EvidenceCritique`, `EvidenceAuthorityScore`,
  `IndependenceCluster`, `SourceTier`, `EvidenceFlag`.
- `orchestrator/evidence_critic.py`: pure function computing authority scores from
  `source_type`, `reliability`, `directness`, recency and limitation disclosure; independence
  clustering; corpus-level statistics.
- New stage `CaseStage.EVIDENCE_CRITIQUE` immediately after `INVESTIGATION`.
- `cursor/roles/researcher.md`: explicit source-authority hierarchy so the researcher aims higher.

**Stage gates with teeth**

- `orchestrator/artifacts/gates.py`: `GateReport`, `GateFinding`, `GateSeverity`.
- `orchestrator/gates.py`: deterministic checks (citation integrity, assumption coverage,
  independence concentration, task health, analysis reproducibility, confidence coherence),
  written to `shared/gates/<stage>.yaml`.
- The Auditor is actually invoked, at the CHALLENGE-stage checkpoint, and the stop
  evaluator's inputs are computed deterministically from gate blocking findings, open
  objections, and coverage. *(Amended 2026-08-06: the sheet previously said "invoked once,
  at the post-investigation boundary" and that "its `AuditStopInput` feeds the stop
  evaluator". The Auditor sits in the CHALLENGE StepPlan — `orchestrator/state_machine.py` —
  and `AuditFinding.stop_input` is written and test-validated but has no orchestrator
  consumer; the enforcement this bullet intended shipped via the deterministic gate path
  below instead. Found in the 2026-08-06 spec sweep.)*
- Enforcement: blocking findings (a) cancel non-material failed tasks through
  `TaskGraph.cancel_tasks`, and (b) force `open_critical_evidence_gaps=True` in the stop
  evaluator so a broken chain cannot stop early.

**Reviewer verification**

- `orchestrator/artifacts/verification.py`: `VerificationWorksheet`, `CitationCheckItem`,
  `CitationVerdict`.
- `orchestrator/verification.py`: deterministic pre-checks (false precision, confidence
  inversion, dangling citations, undisclosed open objections, stability inconsistency) plus
  construction of a per-claim citation worksheet pairing each sampled claim with the excerpts
  of the evidence it cites.
- `ReviewReport` gains `citation_verdicts`.
- `REVIEW` may route back to `SYNTHESIS` once (`CaseState.synthesis_retries`).

## Out of scope

- Live re-fetching of cited URLs (north star open question 8).
- Replacing the coercion layer; it stays as the last line of defence.
- Any change to the four uncertainty measures or how they are computed.

## Design

Deterministic first, model second. Everything that can be computed from the blackboard is
computed in Python and written as an artifact; the agent passes only supply judgement that code
cannot produce (which assumptions are load-bearing, whether an excerpt actually supports a claim).

Authority scoring is a weighted sum, deliberately simple and inspectable:

```
tier_weight(source_type) * 0.5 + reliability * 0.2 + directness * 0.2 + recency * 0.1
```

with a penalty when the evidence's `independence_group` covers more than 40% of the corpus.

Gate outcome is the maximum severity of its findings. A `block` never silently mutates an
artifact; it is recorded, it may cancel tasks, and it changes the stop decision.

## Deliverables

- [x] `orchestrator/artifacts/assumptions.py` — `AssumptionBatch`
- [x] `orchestrator/artifacts/evidence_critique.py`
- [x] `orchestrator/artifacts/gates.py`
- [x] `orchestrator/artifacts/verification.py`
- [x] `orchestrator/evidence_critic.py`
- [x] `orchestrator/gates.py`
- [x] `orchestrator/verification.py`
- [x] `orchestrator/unpack.py` — `unpack_assumption_batch`
- [x] `cursor/roles/assumption_analyst.{md,yaml}`
- [x] stages `EVIDENCE_CRITIQUE`, `ASSUMPTION_LEDGER`; `REVIEW → SYNTHESIS` retry edge
- [x] tests covering each of the four mechanisms

## Acceptance criteria

- [x] A stub pipeline run produces at least one `AssumptionRecord` on the blackboard.
- [x] `EvidenceCritique` exists after a run and its `primary_source_share` and `max_cluster_share`
      match hand-computed values in a unit test.
- [x] A gate with a blocking finding cancels the targeted task and is visible in
      `shared/gates/` and the audit log.
- [x] A `FinalRecommendation` with a dangling citation and an inverted confidence pair produces
      deterministic findings in the verification worksheet.
- [x] A failing `ReviewReport` routes the case back to `SYNTHESIS` exactly once.
- [x] `make check` passes.

## Verification plan

`uv run pytest tests/test_evidence_critic.py tests/test_gates.py
tests/test_verification.py tests/test_pipeline_stub.py`, then `make check`, then the live
benchmark suite in SPEC-026. *(Amended 2026-08-06: the plan previously named
`tests/test_assumption_ledger.py`, which was never created; assumption-ledger coverage lives
in `tests/test_pipeline_stub.py`, `tests/test_gates.py`, and
`tests/test_roles_phase6_live.py`.)*

## Verification results

2026-08-02. `make check` green (lint, mypy, 296 unit tests). Stub pipeline asserts assumption
records, evidence critique, gate reports and citation verdicts are all produced. Deterministic
verification is complete; the live benchmark leg (SPEC-026) has not been run, so the spec stays
`implemented` rather than `verified`.

## Open questions

None.
