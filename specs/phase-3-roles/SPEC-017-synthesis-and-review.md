---
id: SPEC-017
title: Synthesizer and calibration/citation reviewer
phase: 3
status: draft
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-016]
north_star_refs: ["6.8", "6.9", "9", "16"]
last_updated: 2026-07-30
---

# SPEC-017 — Synthesizer and calibration/citation reviewer

## Summary

The finalization pair: the Synthesizer integrates the full normalized decision package into a `FinalRecommendation`, a combined calibration/citation reviewer inspects it, and a deterministic renderer produces the user-facing Markdown with inline citations.

## Motivation

North star 6.8/6.9 and Section 16: the final output must explain dominance rather than average opinions, keep uncertainty measures distinct, disclose stopping reasons, and place citations next to claims.

## Scope

- `cursor/roles/synthesizer.md`: consume decision spec, preliminary recommendation, objections and resolutions, analysis results, disclosure records; produce `FinalRecommendation` covering all Section 16 blocks (executive recommendation, confidence explanation, alternatives ranking, key reasons, scenarios, quantitative findings, counterarguments and their status, critical assumptions, change-triggers, next actions), every material claim carrying E-/A- references; averaging agent opinions explicitly prohibited; unresolved disagreement reported as such (Section 21 question 11).
- `cursor/roles/reviewer.md` (calibration + citation, one role for MVP per 6.9): verify probability statements have basis fields and no false precision, confidence language matches evidence confidence, every citation ID exists and supports its claim (against stored evidence only, not live sources), independence overstatement flagged; output `ReviewReport` (pass | fail with itemized defects); a fail routes the Synthesizer once through the retry ladder with defects as feedback.
- `orchestrator/render.py`: deterministic `FinalRecommendation` + evidence ledger → `outputs/final_recommendation.md` per Section 16 layout, inline `[E-xxx]` citations with a source table, budget-stop disclosure section when a DisclosureRecord exists, and per-statement provenance labels distinguishing sourced facts, assumptions, calculations, user-supplied input, interpretation, and recommendations (Section 15).
- `cursor/roles/synthesizer.yaml`, `cursor/roles/reviewer.yaml`: synthesizer on Director-tier family, reviewer on a precise mid-tier model from a different family; projections.

## Out of scope

Reopening live sources for citation verification (north star open question 8; emergent-work candidate), PDF/HTML rendering.

## Design

Renderer is pure and unit-tested: a golden FinalRecommendation fixture renders to a byte-stable Markdown file. Model stability is computed deterministically by the SPEC-013 stability function and injected as a synthesizer input; the Synthesizer reports it and never invents it. The reviewer never edits the recommendation; it only reports defects, keeping authorship traceable. `ReviewReport` pass is a hard gate before the case may enter `AWAITING_FINAL_APPROVAL`.

## Deliverables

- [ ] `cursor/roles/synthesizer.md`, `cursor/roles/reviewer.md`
- [ ] `ReviewReport` model + schema export
- [ ] `orchestrator/render.py`
- [ ] `cursor/roles/synthesizer.yaml`, `cursor/roles/reviewer.yaml`
- [ ] `tests/test_render.py` (golden output), `tests/test_role_synthesis.py` + fixtures; live mini-run tests

## Acceptance criteria

- [ ] Fixture replay: FinalRecommendation contains all Section 16 blocks, all citations resolve, distinct uncertainty fields present; a fixture with a dangling citation fails validation.
- [ ] Reviewer fixture: planted false-precision probability (e.g. 51.7% from weak evidence) and planted unsupported citation are both flagged; clean fixture passes.
- [ ] Renderer golden test: byte-identical Markdown across runs; disclosure section appears iff a DisclosureRecord exists.
- [ ] Live mini-runs (both roles) produce schema-valid artifacts in ≤2 attempts each.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_render.py tests/test_role_synthesis.py -q
uv run pytest -m live -k "synthesizer or reviewer" -q
```

## Verification results

—

## Open questions

- None.
