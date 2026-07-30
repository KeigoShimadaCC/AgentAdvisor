---
id: SPEC-010
title: Intake and framing roles
phase: 3
status: verified
depends_on: [SPEC-006]
parallel_with: [SPEC-011, SPEC-012, SPEC-013, SPEC-014, SPEC-015, SPEC-016, SPEC-017]
north_star_refs: ["6.1", "8"]
last_updated: 2026-07-31
---

# SPEC-010 — Intake and framing roles

## Summary

The first two model-facing steps: extract a structured intake from the user's raw prompt, then have the Director produce a decision specification with a deliberately broadened alternative set and the framing-approval artifact.

## Motivation

North star Stage 1–2: research must not start until the decision is framed and the user approves the framing (Section 14/15 approval gate).

## Scope

- `cursor/roles/intake.md`: extract decision question, deadline, alternatives mentioned, objectives, constraints, risk tolerance, reversibility, depth; emit explicit `unknown` rather than inventing values; produce ≤5 clarification questions only where an assumption would be material (Stage 1 guidance).
- `cursor/roles/director-framing.md`: from the intake, produce a full `DecisionSpec` with a broadened alternative set (for the investment vertical: staged entry, smaller amount, wait-for-milestone, alternative vehicle, decline-and-revisit patterns per Stage 2) plus initial known-unknowns.
- New artifacts in SPEC-003 module: `IntakeRecord` (extraction + clarifications) and `FramingApproval` (user decision: approve | edit | answers to clarifications).
- Per-role configs `cursor/roles/intake.yaml` and `cursor/roles/director-framing.yaml` (intake: cheap model; framing: Director-tier model; projections).
- Golden fixtures: two sample prompts (one investment, one deliberately vague) with expected-structure assertions (field presence and constraints, not exact text).

## Out of scope

The CLI surface for answering clarifications (SPEC-019), any research or thesis work (SPEC-011/014).

## Design

Fixture assertions are structural: valid `DecisionSpec`, ≥5 alternatives for the investment fixture, every user-stated constraint represented, clarifications only for fields marked `unknown`. Live mini-run uses the vague prompt and asserts schema validity plus the alternatives floor, tolerating content variation.

## Deliverables

- [x] `cursor/roles/intake.md`, `cursor/roles/director-framing.md`
- [x] `IntakeRecord`, `FramingApproval` models + schema exports
- [x] `cursor/roles/intake.yaml`, `cursor/roles/director-framing.yaml`
- [x] `tests/test_role_framing.py` + fixtures; live mini-run test

## Acceptance criteria

- [x] Both fixtures produce schema-valid artifacts via StubBackend replay in unit tests.
- [x] Investment fixture framing yields ≥5 alternatives including at least one not present in the prompt.
- [x] Intake never fabricates: fields absent from the prompt are `unknown` in the fixture replay.
- [x] Live mini-run (cheap model) produces schema-valid IntakeRecord and DecisionSpec in ≤2 attempts each.
- [x] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_framing.py -q
uv run pytest -m live -k framing -q
```

## Verification results

**2026-07-31 — PASS.** `cursor/roles/intake.md` enforces hard anti-fabrication rules (unstated fields are null, never `"unknown"`/`"TBD"`, clarifications only for materially consequential nulls, max 5). `cursor/roles/director-framing.md` broadens the alternative set for investment decisions (smaller amount, staged entry, wait-for-milestone, alternative vehicle, decline-and-revisit). Two structural unit tests pass (investment + vague fixtures), the live mini-run passed in ≤2 attempts each using `composer-2.5` (intake) and `claude-opus-5-thinking-high` (framing). Framing now uses the native `variant="framing"` parameter on `invoke()` introduced in SPEC-006 during Phase 3, so `director-framing.yaml` is loaded directly rather than through a workaround. Projection for `intake_record` now resolves through the canonical `case_store` path (`shared/intake_record.yaml`) after the projection fix, eliminating the hand-seeded `outputs/` path the first implementation required.

## Open questions

- None.
