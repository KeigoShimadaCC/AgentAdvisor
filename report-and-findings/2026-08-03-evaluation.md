# Comparative Evaluation: Multi-Agent Workflow vs Single-Agent Baseline

**Date:** 2026-08-03
**Specs:** SPEC-021, SPEC-022
**Backend:** Droid CLI (`AGENTADVISOR_BACKEND=droid`)
**Models:** Baseline: `gpt-5.4` (single shot) | Workflow: per-role model table (droid)

---

## 1. Executive summary

The multi-agent workflow beats the single-agent baseline on decision quality across all three
benchmark scenarios. The workflow averages **1.93** versus the baseline's **1.44** on the 5-dimension
rubric (out of 2.0), a **+0.49** improvement (34%). The largest gains are in traceability (+1.0),
analytical quality (+0.75), and adversarial robustness (+0.67). The workflow costs ~17x more tokens
and ~9x more wall-clock time, but produces structurally superior output: reproducible quantitative
analysis, repair cycles that revise the thesis, and a complete artifact chain from intake to
recommendation.

The baseline is competitive on decision completeness (both score 2.0) and produces genuinely useful
single-shot recommendations with web-sourced evidence. Its structural ceiling is set by being a
single invocation: it cannot repair, cannot produce reproducible code, and cannot build an audit
chain.

---

## 2. Scoring methodology

Two scorers were used:

- **Developer-scored (baseline):** The baseline outputs (`recommendation.md` for each scenario)
  were read in full and scored against all 17 criteria in `benchmarks/rubric.yaml`. This is the
  developer acting as a surrogate for the user scorer (user directed autonomous completion).
- **Model-assisted (workflow):** The workflow outputs were scored by a reviewer-role model during
  the Phase 6 reruns. The model scored 10 of 17 criteria (the remaining 7 were not in the reviewer's
  contract). Scores are from the `scoring` field of each run's `e2e_summary.json`.

This asymmetry is a known gap: the model-assisted scorer did not evaluate relevance/efficiency or
several sub-criteria. The comparison below uses the 5 dimensions scored by both sides. Score sheets
are committed under `benchmarks/results/scores/`.

---

## 3. Per-scenario results

### Score comparison (5 common dimensions)

| Scenario | Baseline score | Workflow score | Delta | Verdict |
|----------|---------------:|---------------:|------:|---------|
| 01 — Nvidia vs SOXX | 1.46 | **2.00** | +0.54 | workflow wins |
| 02 — Angel startup check | 1.46 | **1.87** | +0.41 | workflow wins |
| 03 — Build vs buy | 1.40 | **1.93** | +0.53 | workflow wins |
| **Average** | **1.44** | **1.93** | **+0.49** | **workflow wins all** |

### Per-dimension comparison (averages across 3 scenarios)

| Dimension | Baseline avg | Workflow avg | Delta | Note |
|-----------|-------------:|-------------:|------:|------|
| Decision completeness | 2.00 | 2.00 | 0.00 | Tie: baseline already excellent |
| Evidence quality | 1.56 | 1.67 | +0.11 | Workflow slightly better (source limitations) |
| Analytical quality | 1.25 | 2.00 | +0.75 | Workflow has reproducible code + sensitivity tables |
| Adversarial robustness | 1.33 | 2.00 | +0.67 | Workflow has repair cycles; baseline cannot revise |
| Traceability | 1.00 | 2.00 | +1.00 | Workflow has full artifact chain; baseline has none |
| Relevance/efficiency | 1.50 | — | — | Not scored for workflow (gap) |

The traceability gap is structural, not stochastic: the baseline has no intake/framing/evidence
artifacts, no assumption ledger, and no objection records. The analytical quality gap reflects the
workflow's `analysis/` directory with runnable code versus the baseline's inline prose arithmetic.

---

## 4. Usage-vs-quality table

| Scenario | Type | Tokens | Time | Score | Evidence | Assumptions | Objections |
|----------|------|-------:|-----:|------:|---------:|------------:|-----------:|
| 01 | Baseline | 124,360 | 5.3 min | 1.46 | — | — | — |
| 01 | Workflow | 1,393,391 | 37.1 min | 2.00 | 33 | 8 | 7 |
| 02 | Baseline | 68,861 | 3.4 min | 1.46 | — | — | — |
| 02 | Workflow | 1,534,989 | 35.0 min | 1.87 | 17 | 7 | 6 |
| 03 | Baseline | 75,465 | 4.3 min | 1.40 | — | — | — |
| 03 | Workflow | 1,751,645 | 37.0 min | 1.93 | 46 | 8 | 7 |
| **Avg** | **Baseline** | **89,562** | **4.3 min** | **1.44** | | | |
| **Avg** | **Workflow** | **1,560,008** | **36.4 min** | **1.93** | **32** | **7.7** | **6.7** |

**Cost per quality point:** Baseline = 62k tokens/point. Workflow = 808k tokens/point. The workflow
costs ~13x more tokens per rubric point, but produces structurally different output that the rubric
partially captures (artifact chain, repair cycles, reproducible code) and that the baseline
structurally cannot produce.

---

## 5. Weakest-role analysis

From the Phase 6 before/after report and the SPEC-020 real case:

1. **Synthesizer** — The highest-value defect found. In case-014 (SPEC-020), the synthesizer
   received truncated inputs (missing preliminary recommendation, objection resolutions, pre-mortem
   indicators), causing both review attempts to fail on uncited claims and an undisclosed open
   objection. Filed as emergent work: synthesis projection must guarantee these artifacts are
   present.

2. **Researcher (scenario 02)** — Produced only 17 evidence records (vs 33-46 in other scenarios)
   with authority mean 0.64. Evidence quality scored 1.33, capping the overall score at 1.87. This
   is the next evidence-quality target after the synthesizer fix.

3. **Reviewer** — In case-014, both review attempts produced all-unsupported verdicts. The root
   cause is the synthesis truncation (the reviewer correctly identified uncited claims, but the
   synthesizer never received the data to cite), so this is a downstream symptom of issue 1.

---

## 6. Repeated-run consistency

Two scenarios were run twice (Phase 6 reruns, both on droid):

| Scenario | Run | Case | Score | Tokens | Invocations | Evidence |
|----------|-----|------|------:|-------:|------------:|---------:|
| 01 | primary | case-006 | 2.00 | 1,393k | 29 | 33 |
| 01 | repeat | case-007 | 2.00 | 1,795k | 31 | 34 |
| 03 | primary | case-008 | 1.93 | 1,752k | 32 | 46 |
| 03 | repeat | case-009 | 1.87 | 1,677k | 33 | 46 |

**Scenario 01:** Perfectly repeatable (both 2.00). Token cost varied 29% (1.39M vs 1.80M) but
quality was stable.

**Scenario 03:** Score varied 0.06 (1.93 vs 1.87), driven by evidence quality (1.67 vs 1.33). The
evidence count was identical (46) but the authority scores differed. This is acceptable
repeatability for a stochastic LLM pipeline.

---

## 7. Tuning iterations

Phase 6 (SPEC-023 through SPEC-026) was the tuning phase. Four defect fixes were applied during
the Phase 6 sweep, all documented in `report-and-findings/2026-08-03-phase-6-before-after.md`:

1. **Budget counter persistence bug** — cases reported zero consumption. Fixed.
2. **Optional-list coercion gap** — killed scenario 03. Fixed.
3. **Role contracts teaching wrong schemas** — caused validation failures. Fixed.
4. **Unquoted YAML colons** — discarded researcher batches. Fixed.

Results: average score 1.89 → 1.96, invocation success 52% → 92%, token cost -40%, assumptions
0 → 7.8/case. No further tuning iterations were needed after Phase 6.

---

## 8. Overall verdict

**The workflow is better than the single-agent baseline.** It wins on all 3 benchmark scenarios,
on 4 of 5 scored dimensions (tying on decision completeness), and produces structurally superior
output that the baseline cannot produce: a complete artifact chain, repair cycles, reproducible
quantitative analysis, and explicit assumption ledgers. The cost is ~17x more tokens and ~9x more
time, which is acceptable for a personal decision-intelligence platform where decision quality is
the top priority (per AGENTS.md priority ordering).

The baseline is not bad — it produces genuinely useful, well-sourced recommendations in under 5
minutes. For time-constrained decisions where traceability and repair are not needed, the baseline
is a reasonable fallback. The workflow's value is in the inspectable chain from evidence to
recommendation, the adversarial process, and the reproducible analysis.

---

## 9. Limitations and future work

- **Scorer asymmetry:** Baseline was developer-scored on 17 criteria; workflow was model-scored
  on 10. A future run should score both with the same scorer on all criteria.
- **Relevance/efficiency not scored for workflow:** The model-assisted scorer's contract did not
  include this dimension.
- **Calibration:** Not assessed (requires outcome history per north star Section 9; explicitly
  future work).
- **Synthesis projection truncation:** The highest-value defect (found in SPEC-020) is filed as
  emergent work. Fixing it should raise the workflow's review pass rate and overall score.
- **Backend comparison:** All runs in this evaluation used the Droid CLI backend. The Cursor CLI
  backend was used in earlier phases but its benchmark scores are not directly comparable due to
  different model availability.
