---
id: SPEC-014
title: Director thesis and preliminary recommendation
phase: 3
status: verified
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-012, SPEC-013, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.1", "8", "9"]
last_updated: 2026-07-31
---

# SPEC-014 — Director thesis and preliminary recommendation

## Summary

The Director's two thesis moments: the early provisional thesis (Stage 3) that gives research direction and the Challenger a target, and the evidence-grounded preliminary recommendation (Stage 6).

## Motivation

North star 6.1: the Director owns the substantive decision, interprets evidence, and maintains the thesis; Section 9 forbids collapsed uncertainty measures from the very first thesis onward.

## Scope

- `cursor/roles/director.md` with two task modes (`mode: provisional_thesis`, `mode: preliminary_recommendation` in `task.yaml`):
  - Provisional thesis: preferred alternative + rationale + the uncertainties that would most plausibly change it; explicitly labeled non-final.
  - Preliminary recommendation: `PreliminaryRecommendation` artifact citing evidence IDs (`E-*`) and assumption IDs (`A-*`) for every material claim, with recommendation confidence and evidence confidence as separate fields, outcome estimates expressed as `ProbabilityEstimate`s (base-rate-first per Section 9), unresolved gaps, and major risks (Stage 6 list).
- Assumption maintenance: the Director may propose new/updated `AssumptionRecord`s; orchestrator merges by ID (updates audited).
- `cursor/roles/director.yaml`: Director-tier model (claude-opus-5 family per research report); projection: decision spec, normalized evidence ledger summaries, assumption registry, analysis results, prior thesis.
- Fixtures: a populated mini-blackboard (evidence + assumptions + analysis) with structural assertions on citation coverage.

## Out of scope

Challenge handling (SPEC-015 produces objections; repair routing is SPEC-018), final synthesis (SPEC-017), framing (SPEC-010).

## Design

Citation coverage is enforced structurally: every entry in the recommendation's `key_reasons` and `estimated_outcomes` must reference ≥1 `E-*` or `A-*` ID, via citation-coverage rules registered on the invocation kit's cross-field validation hook (owned by SPEC-006). Uncited reasons fail validation and trigger the retry ladder.

## Deliverables

- [x] `cursor/roles/director.md`
- [x] Citation-coverage rules registered on the SPEC-006 cross-field validation hook
- [x] `cursor/roles/director.yaml`
- [x] `tests/test_role_director.py` + mini-blackboard fixtures; live mini-run test

## Acceptance criteria

- [x] Fixture replay: preliminary recommendation schema-valid; every key reason cites ≥1 existing E-/A- ID; dangling IDs rejected.
- [x] Recommendation confidence and evidence confidence are distinct fields with values; a fixture collapsing them fails validation.
- [x] Provisional-thesis mode output labeled non-final and lists ≥3 reversal-relevant uncertainties.
- [x] Live mini-run over the fixture blackboard yields a valid PreliminaryRecommendation in ≤2 attempts.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_director.py -q
uv run pytest -m live -k director -q
```

## Verification results

**2026-07-31 — PASS.** `cursor/roles/director.md` branches on `task.yaml` `mode`: `provisional_thesis` (non-final label, ≥3 reversal uncertainties) and `preliminary_recommendation` (full `PreliminaryRecommendation` with base-rate-first `ProbabilityEstimate`s and separate `ConfidenceAssessment` values). `orchestrator/citations.py` registers cross-field hooks on `preliminary_recommendation`: every `key_reasons` and `estimated_outcomes` entry must cite ≥1 existing `E-`/`A-` ID (dangling IDs rejected), and collapsed confidence (identical value AND identical basis string) is rejected as a heuristic. Four unit tests pass (valid replay, dangling-ID rejection, collapsed-confidence rejection, provisional-thesis structure). The live mini-run initially used a fabricated `composer-2.5` config instead of the real `director.yaml`; this was fixed to load `claude-opus-5-thinking-high` natively, and the role md was enriched with explicit field-type constraints and a valid YAML template. The live run then passed in 1 attempt using the real configuration.

## Open questions

- None.
