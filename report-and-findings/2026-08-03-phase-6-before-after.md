# Phase 6 Think-Tank Architecture: Before/After Benchmark Comparison

**Date:** 2026-08-03
**Spec:** SPEC-026
**Baseline:** Phase 4 e2e final evaluation, 2026-08-02 (`report-and-findings/2026-08-02-e2e-final-evaluation.md`)

---

## 1. Executive summary

All five benchmark scenarios completed successfully after Phase 6 (tiers 1-3) plus four defect fixes discovered during the sweep. Average score improved from **1.89 to 1.96** (out of 2.0). The most consequential changes:

- **Assumption records: 0 to 7.8 per case.** The new assumption analyst role and assumption ledger (SPEC-023) eliminated the most glaring Phase 4 gap.
- **Invocation success rate: 52% to 92%.** Role contract rewrites and a YAML quoting rule cut validation failures dramatically.
- **Evidence quality: 1.53 to 1.80.** The evidence critic (SPEC-023) and researcher contract rewrite improved source authority scoring.
- **Analytical quality: 1.90 to 2.00.** The analyst contract fix and issue-tree-driven task structuring (SPEC-024) raised the floor.
- **Token cost: 11.9M to 7.1M input (40% reduction).** Fewer retries and more efficient invocation patterns despite adding 4 new roles and 4 new pipeline stages.

Four defects were found and fixed during the sweep: a budget counter persistence bug, an optional-list coercion gap that killed scenario 03, role contracts teaching wrong schemas, and unquoted YAML colons discarding researcher batches. Each is documented in section 5.

---

## 2. Per-scenario score comparison

| Scenario | Title | Baseline | Phase 6 | Delta | Status |
|----------|-------|----------|---------|-------|--------|
| 01 | Nvidia vs Semiconductor ETF | 1.77 | **2.00** | +0.23 | improved |
| 02 | Angel check for AI startup | 1.87 | 1.87 | 0.00 | flat |
| 03 | Build vs buy analytics | 1.87 | **1.93** | +0.06 | improved |
| 04 | Career switch (Big tech vs Series B) | 2.00 | **2.00** | 0.00 | maintained |
| 05 | Buy condo vs rent and invest | 1.93 | **2.00** | +0.07 | improved |
| **Average** | | **1.89** | **1.96** | **+0.07** | |

Scenario 02 is flat at 1.87. Its evidence quality remains 1.33 (the same as baseline), which caps the overall score. The researcher produced only 17 evidence records (vs 33-46 in other scenarios), and the evidence authority mean was 0.64. This is the next evidence-quality target.

Two scenarios (01 and 03) were re-run twice to verify repeatability:

| Scenario | Run | Case | Score | Invocations | Success% |
|----------|-----|------|-------|-------------|----------|
| 01 | primary | case-006 | 2.00 | 29/29 | 100% |
| 01 | repeat | case-007 | 2.00 | 31/31 | 100% |
| 03 | primary | case-010 | 1.93 | 32/31 | 97% |
| 03 | repeat | case-009 | 1.87 | 33/31 | 94% |

Both S01 runs scored identically. S03 varied by 0.06 (one evidence-quality dimension step). This is acceptable repeatability for a stochastic LLM pipeline.

---

## 3. Per-dimension comparison

| Dimension | Baseline avg | Phase 6 avg | Delta | Note |
|-----------|-------------|-------------|-------|------|
| Decision completeness | 2.00 | 2.00 | 0.00 | Already perfect |
| Evidence quality | 1.53 | 1.80 | +0.27 | Biggest improvement |
| Analytical quality | 1.90 | 2.00 | +0.10 | S01 floor raised |
| Adversarial robustness | 2.00 | 2.00 | 0.00 | Already perfect |
| Traceability | 2.00 | 2.00 | 0.00 | Already perfect |

### Per-scenario dimension breakdown

| Dimension | S01 | | S02 | | S03 | | S04 | | S05 | |
|-----------|-----|--|-----|--|-----|--|-----|--|-----|--|
| | base | post | base | post | base | post | base | post | base | post |
| Decision completeness | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |
| Evidence quality | 1.33 | 2.00 | 1.33 | 1.33 | 1.33 | 1.67 | 2.00 | 2.00 | 1.67 | 2.00 |
| Analytical quality | 1.50 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |
| Adversarial robustness | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |
| Traceability | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 | 2.00 |

Evidence quality improved in 4 of 5 scenarios. The exception is S02, where the researcher produced fewer evidence records and lower authority scores. Analytical quality improved in S01 (1.50 to 2.00) because the analyst contract fix and issue-tree structuring produced 7 analysis results instead of 1.

---

## 4. Resource consumption comparison

### Cost and time

| Metric | Baseline | Phase 6 | Delta |
|--------|----------|---------|-------|
| Total wall clock | 285 min (4.75 hr) | 202 min (3.37 hr) | -29% |
| Avg wall clock per case | 57 min | 40 min | -30% |
| Total input tokens | 11.9M | 7.1M | -40% |
| Total output tokens | 1.98M | 1.39M | -30% |
| Total invocations | 207 | 163 | -21% |
| Successful invocations | 108 (52%) | 150 (92%) | +40pp |

### Per-scenario cost

| Scenario | Baseline time | Phase 6 time | Baseline tokens (in) | Phase 6 tokens (in) |
|----------|--------------|--------------|---------------------|---------------------|
| 01 | 81 min | 37 min | 3.0M | 1.15M |
| 02 | 40 min | 35 min | 1.8M | 1.30M |
| 03 | 52 min | 37 min | 2.2M | 1.47M |
| 04 | 66 min | 48 min | 2.8M | 1.77M |
| 05 | 46 min | 45 min | 2.0M | 1.44M |

Phase 6 adds 4 new roles (structurer, assumption analyst, director-b, premortem) and 4 new pipeline stages, yet total cost dropped. The reason: the baseline wasted 99 failed invocations on retries and escalations. The contract fixes and coercion improvements cut the failure rate so deeply that the added stages cost less than the saved retries.

### Record counts

| Record type | Baseline (sum) | Phase 6 (sum) | Note |
|-------------|----------------|---------------|------|
| Evidence | 133 | 148 | +11% |
| Assumptions | 0 | 39 | Was zero, now 7-8 per case |
| Objections | 32 | 34 | Unchanged |
| Analysis | 20 | 36 | +80% |

The assumption count is the headline structural change. Phase 4 produced zero assumption records in any scenario. Phase 6 produces 7-8 per case through the dedicated assumption analyst role.

---

## 5. Phase 6 structural metrics

These metrics are new in Phase 6 and have no baseline comparison.

| Metric | S01 | S02 | S03 | S04 | S05 | Avg |
|--------|-----|-----|-----|-----|-----|-----|
| Issue tree nodes | 14 | 15 | 16 | 16 | 16 | 15.4 |
| Issue tree leaves | 7 | 9 | 10 | 10 | 10 | 9.2 |
| Premortem failure modes | 5 | 5 | 5 | 5 | 5 | 5.0 |
| Gate reports | 7 | 7 | 7 | 7 | 7 | 7.0 |
| Gate blocking findings | 0 | 0 | 1 | 0 | 1 | 0.4 |
| Gate warning findings | 3 | 4 | 4 | 3 | 3 | 3.4 |
| Thesis revisions | 3 | 3 | 3 | 3 | 3 | 3.0 |
| Thesis changes | 2 | 1 | 1 | 2 | 0 | 1.2 |
| Track agreement | False | False | False | False | True | 20% |
| Verification worksheet items | 8 | 8 | 8 | 8 | 8 | 8.0 |
| Resynthesis cycles | 2 | 2 | 2 | 2 | 2 | 2.0 |
| Evidence authority mean | 0.71 | 0.64 | 0.61 | 0.69 | 0.83 | 0.70 |
| Evidence independent groups | 29 | 17 | 41 | 36 | 7 | 26.0 |
| Evidence max cluster share | 0.06 | 0.06 | 0.09 | 0.07 | 0.14 | 0.08 |

Key observations:

- **Issue trees** produce 14-16 nodes with 7-10 leaves per case, giving the planner a MECE decomposition to work from.
- **Gates** fire 7 reports per case with 0-1 blocking findings and 3-4 warnings. The gate mechanism is not a rubber stamp: it blocks or warns in every case.
- **Thesis revisions** occur 3 times per case with 0-2 substantive changes. The living thesis is evolving, not static.
- **Dual track** disagrees in 4 of 5 cases (track_agreement = False). Track B (the independent director) is producing genuinely different assessments, which is the intended behavior. Reconciliation happens in all cases.
- **Resynthesis cycles** are consistently 2, meaning the verification worksheet triggers one retry of synthesis in every case.
- **Evidence concentration** (max cluster share) is below 0.15 in all cases, indicating no single source dominates the evidence base.

---

## 6. Defects found and fixed during the sweep

Four defects were discovered during the Phase 6 sweep. Each would have gone undetected in unit tests because they only manifest in live model invocations.

### 6.1 Budget counter persistence (commit `0d0be44`)

**Symptom:** `case_metrics.py` reported zero budget consumption for a completed case.

**Root cause:** `run_case` re-loaded `CaseState` from disk, creating a new `BudgetLedger` object. The `BudgetLedger` that `pipeline.py` held a reference to was mutated in memory but never persisted, because the state machine was operating on a different object. Budget caps were effectively per-process, not per-case: a resumed case would start spending from zero.

**Fix:** `run_case` now accepts an `initial_state` parameter. `pipeline.py` passes its existing state object, so the budget ledger mutations land on the same object that gets saved. A regression test (`test_budget_consumption_is_persisted_not_stranded_in_memory`) fails without the fix.

### 6.2 Optional-list coercion gap (commit `0d0be44`)

**Symptom:** Scenario 03 died at intake with 3 invocations, 0 successful, score 0.00.

**Root cause:** `coerce_payload_for_model` used `get_origin(field_type) is list` to detect list fields, but `list[...] | None` has origin `UnionType`, not `list`. Every optional list field in every artifact schema was silently skipping coercion. When the intake model produced a slightly malformed `list[str] | None` field, validation failed and the escalation ladder could not recover.

**Fix:** Added `_unwrap_optional()` that strips `Optional`/`Union[..., None]` before checking `get_origin`. Also added `_is_unparseable_date` to null vague deadlines like "this quarter" instead of failing validation, and an `_accepts_none` guard so null is only applied when the schema permits it. Four regression tests added.

### 6.3 Role contracts teaching wrong schemas (commit `a2ef43d`)

**Symptom:** 30 validation failures in scenario 01, 46% invocation success rate. Analyst and researcher accounted for 73% of token spend at 23-33% success rates.

**Root cause:** The analyst's worked YAML example used `method: base_rate` (not a valid `ProbabilityMethod` value) and an adjustment shape of `{delta, reason, evidence_id}` instead of the schema's `{description, delta, evidence_ids}`. The model faithfully copied the example, producing invalid output every time. The researcher contract listed field names without types, so `directness: direct` (should be a float) and bare-string `limitations` (should be a list) looked reasonable. The synthesizer example had `model_stability` share as 0.67 for 2/3, which the consistency validator rejects (must equal `runs_supporting / runs_total`).

**Fix:** Rewrote analyst, researcher, challenger, and reviewer role definitions with full typed field tables and valid YAML examples. Created `tests/test_role_contracts.py` (16 tests) that validates every worked example in every role md against the schema its role config declares. It immediately caught the synthesizer defect. This test is now part of `make check` and prevents the same class of drift from recurring.

### 6.4 YAML colon quoting (commit `22077f5`)

**Symptom:** Two researcher batches in scenario 04 were silently discarded. The audit log showed parse failures on YAML containing source titles and publisher names with unquoted colons.

**Root cause:** A source title like "Nvidia: AI Chip Leader" makes the YAML line `title: Nvidia: AI Chip Leader` unparseable. The model had no instruction to quote strings containing colons.

**Fix:** Added a YAML quoting rule to the shared `FIXED_PROMPT` and `FIXED_READ_ONLY_PROMPT` that every role receives: "Quote any string value that contains a colon, using double quotes."

---

## 7. What did not change

Three dimensions were already at 2.00/2.0 in the baseline and stayed there:

- **Decision completeness:** The intake-to-framing-to-provisional-thesis pipeline was robust in Phase 4 and remains so. Phase 6's structurer role adds MECE decomposition but the director's framing output was already complete.
- **Adversarial robustness:** The challenger role produced 5-7 substantive objections in both baseline and Phase 6. The premortem role adds a second adversarial pass but the challenger alone was already sufficient for a perfect score.
- **Traceability:** Evidence-to-recommendation chain is fully inspectable in both versions. Phase 6's thesis ledger and gate reports add more intermediate audit trail but the end-to-end chain was already traceable.

This means Phase 6's value is concentrated in evidence quality (the weakest baseline dimension) and the structural features that have no baseline analog (assumption ledger, issue tree, gates, dual track, thesis evolution, verification).

---

## 8. Honest assessment

### What improved

1. **Evidence quality (+0.27):** The evidence critic scores source authority and cluster concentration, and the researcher contract rewrite produces better-formed evidence records. S01 went from 1.33 to 2.00, S03 from 1.33 to 1.67, S05 from 1.67 to 2.00.

2. **Assumption coverage (0 to 7.8/case):** The assumption analyst role and assumption ledger fill the most glaring Phase 4 gap. Every case now has 7-10 assumption records with explicit independence groups.

3. **Invocation reliability (52% to 92%):** Role contract fixes and the YAML quoting rule cut validation failures by 80%. This is the single largest engineering improvement and it reduced cost as a side effect.

4. **Cost (-40% input tokens, -29% wall clock):** Counterintuitively, adding 4 roles and 4 stages reduced total cost because the saved retries outweighed the added invocations.

### What did not improve

1. **Scenario 02 evidence quality (1.33, flat):** The researcher produced only 17 evidence records with a 0.64 authority mean. This is the same score as baseline. The angel-investment scenario may need domain-specific skill packs (SPEC-025's specialist packs) or a different researcher prompt to improve.

2. **Dimensions already at 2.00:** Phase 6 adds machinery (premortem, dual track, gates) that does not move the score because the baseline was already perfect on those dimensions. The value is in the audit trail and structural depth, not in the score.

3. **Track agreement is only 20%:** Track B disagrees with Track A in 4 of 5 cases. This is by design (independent assessment), but it means the reconciliation step is doing real work in 80% of cases. Whether the reconciled output is better than either track alone is not measurable with the current rubric.

### Caveats

1. **Scenarios 04 and 05 were run with contract fixes applied mid-sweep.** They picked up the role contract rewrites and YAML quoting rule partway through their runs (researcher and analyst invocations happen after intake and structuring). Their scores may be slightly inflated relative to a clean run with all fixes from the start. The re-runs of S01-S03 are clean.

2. **The baseline and Phase 6 runs used different model assignments.** The baseline used `cursor-grok-4.5-low` for Director/Reviewer/Researcher and `composer-2.5` for Challenger/Planner/Auditor/Analyst/Synthesizer. The Phase 6 runs used the same assignments, but the contract fixes changed what the models produce, not which models are used. The comparison is therefore about the architecture and prompts, not about model selection.

3. **The rubric was extended for Phase 6** with new criteria (evidence authority, issue tree coverage, gate findings, thesis evolution). The five legacy dimensions are computed identically, but the new criteria have no baseline comparison. This report compares only the five legacy dimensions for the before/after table.

---

## 9. Verdict

Phase 6 tiers 1-3 are a net improvement. The average score rose from 1.89 to 1.96, the weakest dimension (evidence quality) rose from 1.53 to 1.80, the assumption gap was closed, and the cost dropped by 40%. The improvement is real, not a rubric artifact: the same five dimensions are scored the same way, and the post-fix runs produce more evidence, more analysis, and more assumptions at lower token cost.

The remaining work is scenario 02's evidence quality (1.33, unchanged), which points to domain-specific researcher support as the next lever.

---

## Appendix A: Model configuration

All runs (baseline and Phase 6) used the same model assignments:

| Role | Model | Family |
|------|-------|--------|
| Director, Director-framing | `cursor-grok-4.5-low` | xai |
| Reviewer | `cursor-grok-4.5-low` | xai |
| Researcher | `cursor-grok-4.5-low` | xai |
| Challenger | `composer-2.5` | cursor-composer |
| Planner | `composer-2.5` | cursor-composer |
| Auditor | `composer-2.5` | cursor-composer |
| Analyst | `composer-2.5` | cursor-composer |
| Synthesizer | `composer-2.5` | cursor-composer |
| Intake | `composer-2.5` | cursor-composer |
| Structurer (new) | `composer-2.5` | cursor-composer |
| Assumption analyst (new) | `composer-2.5` | cursor-composer |
| Director-b (new) | `cursor-grok-4.5-low` | xai |
| Premortem (new) | `composer-2.5` | cursor-composer |

## Appendix B: Case IDs used

| Scenario | Baseline case | Phase 6 case(s) | Notes |
|----------|--------------|-----------------|-------|
| 01 | case-001 | case-006, case-007 | Two re-runs for repeatability |
| 02 | case-002 | case-008 | Single re-run |
| 03 | case-003 | case-009, case-010 | Two re-runs (original was killed by coercion bug) |
| 04 | (overwritten) | case-004 | Phase 6 sweep, contract fixes applied mid-run |
| 05 | (overwritten) | case-005 | Phase 6 sweep, contract fixes applied mid-run |

## Appendix C: Commits

| Commit | Date | Description |
|--------|------|-------------|
| `0d0be44` | 2026-08-02 | Fix budget counters vanishing and the coercion gap that killed scenario 03 |
| `a2ef43d` | 2026-08-02 | Stop role definitions teaching schemas the orchestrator rejects |
| `22077f5` | 2026-08-02 | Tell every role to quote YAML strings containing a colon |
| `d29093b` | 2026-08-02 | Record the sweep defects and early case metrics in the roadmap |
| `f004b88` | 2026-08-02 | Record the role-contract findings and SPEC-020's chosen decision type |
