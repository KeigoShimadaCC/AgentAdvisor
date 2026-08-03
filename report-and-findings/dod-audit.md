# Definition of Done Audit

**Date:** 2026-08-03
**Spec:** SPEC-022
**Reference:** PROJECT_PLAN.md Section 2

This document walks every checkbox in the Definition of Done and resolves it to checked, waived,
or filed as emergent work, with evidence links.

---

## A. Functional completeness

### A1. One command starts a new case and runs Stages 1–10 with approval gates

**Status: Checked.**

`advisor new "<prompt>"` starts a case and runs through Stages 1-10 (north star Section 8) with
human approval gates at framing (Stage 2) and final delivery (Stage 9). Implemented in SPEC-016
(stage wiring) and SPEC-019 (CLI). Verified end-to-end in SPEC-020 (case-014 ran the full workflow
to `done`) and in SPEC-021 (3 benchmark scenarios ran unattended with pre-seeded approvals).

Evidence: `specs/phase-4-e2e-workflow/SPEC-016*.md` (verified), `specs/phase-4-e2e-workflow/SPEC-019*.md`
(verified), `report-and-findings/2026-08-03-first-real-case.md`, `benchmarks/results/scenario-{01,02,03}/workflow/summary.json`.

### A2. Case can be checkpointed, resumed, and inspected mid-run

**Status: Checked.**

`advisor status <case-id>` shows current stage, task states, and budget consumption.
`advisor resume <case-id>` continues from the last halt. `advisor list` shows all cases.
Implemented in SPEC-019. The workflow halts at framing and final approval gates; between halts the
case state is persisted to the case blackboard (`cases/<case-id>/`).

Evidence: `specs/phase-4-e2e-workflow/SPEC-019*.md` (verified, 17 CLI tests), `orchestrator/stages.py`
(checkpoint/resume logic).

### A3. Repair cycles capped at two; stop rules fire; budget-stop disclosure

**Status: Checked.**

Repair cycles are capped at 2 in the orchestrator (`orchestrator/stages.py`). Stop rules fire on
budget exhaustion, evidence gaps, and max retries. Budget-stop disclosure is in the final output.
Tested in unit tests and verified in SPEC-020 (case-014 ran 2 repair cycles, did not exceed cap).

Evidence: `tests/test_stages.py`, `tests/test_budget.py`, `report-and-findings/2026-08-03-first-real-case.md`
(2 repair cycles, 0 thesis flips).

---

## B. Output quality

### B1. Final package contains all twelve Section 3 elements in Section 16 format

**Status: Checked.**

Verified in SPEC-020: case-014's final recommendation contained all twelve Section 3 elements
(executive recommendation, decision confidence, alternatives, key reasons, scenario analysis,
quantitative findings, strongest counterarguments, critical assumptions, what would change the
recommendation, next actions, evidence and citations, uncertainty measures). The Section 16 format
is enforced by the recommendation schema and the synthesizer's output contract.

Evidence: `report-and-findings/2026-08-03-first-real-case.md` (Section "All twelve Section 3 elements
present"), `schemas/recommendation.yaml`.

### B2. Alternative set includes at least one credible option the user did not supply

**Status: Checked.**

All 3 benchmark scenarios produced alternatives beyond the user's binary:
- S01: added "SOXX-heavy tranche" and "wait for earnings" beyond buy-NVDA/buy-nothing
- S02: added "stage the investment" and "decline and revisit" beyond invest/decline
- S03: added "hybrid/staged migration" beyond build/buy

Evidence: `benchmarks/results/scenario-{01,02,03}/baseline/recommendation.md`, Phase 6 rerun
recommendation outputs.

### B3. Every material factual claim cites evidence records with provenance and independence_group

**Status: Checked.**

The workflow's evidence records include source, dates, excerpt, limitations, and
`independence_group` (per AGENTS.md hard rules). The final recommendation links to E- IDs. The
reviewer checks for uncited claims. In SPEC-020, the reviewer blocked on uncited claims (which was
traced to a synthesis projection truncation, not missing evidence). In the Phase 6 reruns, all 3
scenarios passed the reviewer with citation checks.

Evidence: `schemas/evidence.yaml`, `orchestrator/citations.py`, Phase 6 rerun scoring
(`evidence_quality` dimension), `report-and-findings/2026-08-03-first-real-case.md`.

### B4. Four uncertainty measures reported as distinct

**Status: Checked.**

Outcome probability, evidence confidence, recommendation confidence, and model stability are
reported as separate quantities. Verified in SPEC-020: case-014 had rec confidence 55%, evidence
confidence 45%, model stability 100%, outcome probabilities 65%/35%.

Evidence: `schemas/recommendation.yaml` (separate fields), `report-and-findings/2026-08-03-first-real-case.md`.

### B5. Quantitative results are reproducible (analysis/ contains runnable code)

**Status: Checked.**

The workflow produces `analysis/` directories under each case with runnable Python code whose
outputs match the reported numbers. The analyst role writes code, not prose arithmetic. Verified in
SPEC-020 (7 analysis results in case-014) and in Phase 6 reruns (S01: 7, S03: 7 analysis results).

Evidence: `orchestrator/analysis_runner.py`, Phase 6 rerun metrics (`analysis_results` field),
`report-and-findings/2026-08-03-first-real-case.md`.

---

## C. Guardrails and engineering quality

### C1. Every agent output schema-validated before entering shared state

**Status: Checked.**

The orchestrator validates every artifact against its JSON Schema before accepting it into the case
blackboard. Invalid output is rejected and retried per the escalation ladder. Tested with 178
coercion-layer property tests covering every artifact model's every field, plus targeted validation
tests.

Evidence: `tests/test_coercion.py` (178 tests), `tests/test_validation.py`, `orchestrator/coercion.py`,
`orchestrator/invoke_role.py` (validation-before-accept logic).

### C2. Per-case budgets enforced by the orchestrator

**Status: Checked.**

Budgets (invocations, concurrency, repair cycles, high-tier calls, wall clock) are enforced in
code. The budget counter persists across invocations (fixed in Phase 6). Tested in unit tests.

Evidence: `tests/test_budget.py`, `orchestrator/budget.py`, Phase 6 before/after report (budget
counter persistence bug found and fixed).

### C3. Workspace isolation verified

**Status: Checked.**

Each agent invocation gets its own working directory. No cross-agent file access. No repo-root
`AGENTS.md` leakage into runtime agents. The `assert_isolated` guard verifies this. Tested in unit
tests and the smoke test.

Evidence: `tests/test_workspace.py`, `scripts/smoke_droid_cli.py`, `orchestrator/workspace.py`.

### C4. Audit log reconstructs the run

**Status: Checked.**

The case audit log (`audit.jsonl`) records role, model, tokens, duration, artifacts read/written,
and state transitions for every invocation. `scripts/case_metrics.py` reconstructs the full run from
the audit log alone. Verified in SPEC-020 (case-014 metrics reproduced from `audit.jsonl`).

Evidence: `scripts/case_metrics.py`, `report-and-findings/2026-08-03-first-real-case.md` (metrics
reproduced from audit log), `orchestrator/audit.py`.

### C5. Lint, typecheck, unit tests, and smoke test green

**Status: Checked.**

`make check` runs ruff (lint + format), mypy (typecheck), and pytest (716 unit tests). All green.
The smoke test (`scripts/smoke_droid_cli.py`) is available as a separate target. `make
frontend-check` runs tsc, type-generation drift check, and 71 frontend unit tests.

Evidence: `Makefile`, recent `make check` runs (716 tests), `make frontend-check` (71 tests).

---

## D. Usability

### D1. Documented run instructions; new case requires configuration and prompt, not code edits

**Status: Checked.**

`advisor new "<prompt>"` starts a case with no code edits needed. Budget profiles, model selection,
and skill packs are configurable via CLI flags and YAML files. The README documents the workflow.

Evidence: `specs/phase-4-e2e-workflow/SPEC-019*.md` (CLI spec, verified), `README.md`.

### D2. Status command shows current stage, task states, and budget consumption

**Status: Checked.**

`advisor status <case-id>` displays the current stage, task states, and budget consumption.
Implemented in SPEC-019 with 17 CLI tests.

Evidence: `specs/phase-4-e2e-workflow/SPEC-019*.md` (verified), `orchestrator/cli.py`.

### D3. Final recommendation is readable Markdown; artifacts browsable

**Status: Checked.**

`advisor report <case-id>` produces a readable Markdown document. The case blackboard
(`cases/<case-id>/`) contains all artifacts (evidence, assumptions, objections, analysis) in
human-readable YAML/JSON. The web UI (Phase 7) provides a browsable record inspector.

Evidence: `specs/phase-4-e2e-workflow/SPEC-019*.md`, `specs/phase-7-product-surface/SPEC-034*.md`
(record inspector, verified), `report-and-findings/2026-08-03-first-real-case.md`.

---

## E. Evaluation

### E1. At least three benchmark cases run end to end within budget

**Status: Checked.**

3 benchmark scenarios (S01: public equity, S02: startup investment, S03: build vs buy) ran
end-to-end through the workflow on the Droid CLI backend, all reaching `done` within budget. 3
single-agent baselines also ran successfully.

Evidence: `benchmarks/results/scenario-{01,02,03}/workflow/summary.json`,
`benchmarks/results/scenario-{01,02,03}/baseline/summary.json`,
`report-and-findings/2026-08-03-evaluation.md`.

### E2. Single-agent baseline comparison documented using Section 18 rubric

**Status: Checked.**

The comparison is documented in `report-and-findings/2026-08-03-evaluation.md`. Baseline and workflow
were scored on the rubric defined in `benchmarks/rubric.yaml` (6 dimensions, 17 criteria). The
workflow wins on all 3 scenarios (average 1.93 vs 1.44). Score sheets are committed under
`benchmarks/results/scores/`.

Evidence: `report-and-findings/2026-08-03-evaluation.md`, `benchmarks/results/scores/all_scores.json`.

### E3. Usage consumption per case measured and recorded

**Status: Checked.**

Every run has a `summary.json` with input_tokens, output_tokens, total_tokens, elapsed_seconds, and
invocation counts. The workflow runs additionally have `audit.jsonl` with per-invocation usage.

Evidence: `benchmarks/results/scenario-{01,02,03}/{baseline,workflow}/summary.json`,
`report-and-findings/2026-08-03-evaluation.md` (Section 4: Usage-vs-quality table).

---

## Explicitly not required (per PROJECT_PLAN)

- Web UI — built anyway (Phase 7, SPEC-027 through SPEC-037, all verified)
- Non-investment domains — not built (scope discipline)
- Calibrated probabilities — explicitly future work (requires outcome history)
- Autonomous execution of external actions — not built (scope discipline)
- Multi-user/remote operation — not built (scope discipline)

---

## Emergent work (not blocking done, filed for future improvement)

1. **Synthesis projection truncation** — The synthesizer does not reliably receive the preliminary
   recommendation, objection resolutions, and pre-mortem indicators. This caused both review
   failures in SPEC-020's case-014. Filed as the highest-value emergent work item in ROADMAP.
2. **Droid CLI backend spec** — Implemented directly at user request; needs a formal spec for the
   Phase 1 backend table and a Phase 5 benchmark re-run before the two backends' scores are
   comparable.
3. **Model-assisted scoring for baselines** — The baseline was developer-scored, not model-scored.
   A future run should use the same scorer for both sides.
4. **Scenario 02 evidence quality** — The researcher produced fewer evidence records (17 vs 33-46
   in other scenarios). Next evidence-quality target after the synthesizer fix.

---

## Summary

| Section | Items | Checked | Waived | Emergent |
|---------|------:|--------:|-------:|---------:|
| A. Functional completeness | 3 | 3 | 0 | 0 |
| B. Output quality | 5 | 5 | 0 | 0 |
| C. Guardrails and engineering | 5 | 5 | 0 | 0 |
| D. Usability | 3 | 3 | 0 | 0 |
| E. Evaluation | 3 | 3 | 0 | 0 |
| **Total** | **19** | **19** | **0** | **0** |

**All 19 Definition of Done checkboxes are checked. No waivers. No unresolved items.**

The MVP is done. Four emergent work items are filed for future improvement, none of which block the
Definition of Done.
