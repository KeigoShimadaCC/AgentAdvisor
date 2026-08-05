---
id: SPEC-039
title: Independent review with blocking authority, and a limitations statement
phase: 8
status: verified
depends_on: [SPEC-038]
parallel_with: [SPEC-043]
north_star_refs: ["5.3", "6.9", "9", "12", "18"]
last_updated: 2026-08-04
---

# SPEC-039 — Independent review with blocking authority, and a limitations statement

## Summary

Adds the review step every serious analytic shop runs and this pipeline does not: an independent
reviewer, on a third model family, who receives the conclusion and the raw evidence but **not** the
reasoning trail, and answers one question — would you reach this conclusion from this evidence?
Dissent blocks delivery. Adds the companion disclosure a think tank publishes and this system does
not: an explicit statement of what could not be assessed.

`depends_on: [SPEC-038]` is a file-level sequencing constraint, not a logical one — both specs extend
`orchestrator/artifacts/recommendations.py`, and the spec rules say to sequence rather than
parallelize when files overlap.

## Motivation

North star Section 6.9 assigns the review role responsibility for confirming that the final
recommendation "accurately reflects the underlying artifacts," and Section 12 requires model
diversity specifically at the boundary between synthesis and review. The current Reviewer performs
conformance checking — citation integrity, confidence coherence, verification worksheet — which
catches malformed output but cannot catch a well-formed conclusion the evidence does not support.
Nobody currently re-derives the answer.

Section 18 makes traceability a success criterion, and `DisclosureRecord` today discloses only stop
reasons and exhausted budget dimensions. The system never states where the evidence was thin.

## Scope

- `cursor/roles/reviewer-b.{md,yaml}` — the independent reviewer, a `variant` of `TaskRole.REVIEWER`
  resolved through the existing `load_role_config(role, variant)` path, exactly as `director-b` is
  today.
- `backends/cursor/models.yaml` and `backends/droid/models.yaml` — a `reviewer-b` entry on a model
  family different from both the Director and the Challenger.
- `orchestrator/projection.py` — new include key `independent_review_packet`: decision spec, final
  recommendation, the full evidence ledger, the assumption ledger, and the evidence critique.
  Explicitly **excluded**: thesis history, track divergence, objections, pre-mortem, gate reports,
  and any prior reviewer output.
- `orchestrator/artifacts/review.py` — `IndependentVerdict` enum
  (`concur`, `concur_with_reservations`, `dissent`), and `IndependentReview` with
  `verdict`, `reasoning`, `divergent_conclusion` (required when `dissent`), `unsupported_claims`,
  and `evidence_ids`.
- `orchestrator/stages.py::handle_review` — invoke `reviewer-b` after the existing reviewer passes.
  `dissent` produces a blocking gate finding and takes the existing synthesis retry edge. If the
  retry budget is exhausted, the dissent is disclosed verbatim in the final output rather than
  discarded.
- `orchestrator/artifacts/recommendations.py` — `FinalRecommendation.limitations: list[NonEmptyStr]`
  with `default_factory=list`.
- `orchestrator/gates.py` — `review.empty_limitations` finding when the list is empty, and
  `review.unaddressed_dissent` when a dissent survives to delivery.
- `orchestrator/render.py` — a Limitations section, and an "unanswered questions" list built from
  the issue-tree leaves with no completed task (`compute_coverage` already computes this).
- `cursor/roles/synthesizer.md` — contract and worked example for `limitations`.
- `orchestrator/service/lexicon_data.yaml` — narration for the new audit events.

## Out of scope

- Live citation re-verification by reopening sources (north star open question 8; remains out of
  scope as it was in SPEC-017).
- A second independent reviewer, or reviewer voting. One independent verdict, reported as-is.
- Frontend work. The verdict and limitations surface through the existing Method and Challenges
  rooms and the Delivery screen's existing block rendering.

## Design

**Why withhold the reasoning trail.** A reviewer that reads the thesis history and the objections
inherits the anchoring the review exists to detect. Giving it the conclusion plus the raw ledger
forces an independent derivation. This is the RAND pattern — a reviewer technically qualified to
have done the work, who was not on the project.

**Why a variant rather than a new role.** `RoleConfig.variant` and the `stem` property already
resolve `reviewer-b` to its own md, yaml and per-backend model entry. No new `TaskRole` member, no
new stage, no state machine change. The precedent is `director-b`, added in SPEC-024.

**Blocking without deadlock.** Dissent routes to the synthesis retry edge that already exists for
verification failures. The retry budget is unchanged, so a persistent dissent cannot loop: it is
disclosed. Disclosing a dissent the system could not resolve is a better outcome than suppressing
it, and matches the north star's rule that unresolved disagreement is reported as unresolved.

**Limitations content.** Three sources, assembled by the synthesizer and checked by the gate:
evidence gaps already tracked in `unresolved_evidence_gaps`, issue-tree leaves with no completed
task, and claims resting on a single `independence_group`. The first two are already computed; only
the prose is new.

**Cost.** One additional high-tier invocation per case. The budget ledger's `high_tier_calls` cap is
6; measure whether that needs raising before the SPEC-044 benchmark run.

## Deliverables

- [ ] `cursor/roles/reviewer-b.{md,yaml}` and the two `models.yaml` entries
- [ ] `independent_review_packet` projection key with an exclusion test
- [ ] `IndependentVerdict` and `IndependentReview` artifacts
- [ ] `handle_review` wiring, blocking finding, and disclosure-on-exhaustion path
- [ ] `FinalRecommendation.limitations` plus renderer section
- [ ] Two new gate checks
- [ ] `tests/test_independent_review.py`
- [ ] Regenerated `schemas/` and `frontend/src/generated/`

## Acceptance criteria

- [ ] `make check` and `make frontend-check` are green.
- [ ] A test asserts the `independent_review_packet` projection contains the evidence ledger and
      contains **none** of: thesis history, track divergence, objections, pre-mortem, gate reports.
- [ ] `reviewer-b` resolves to a model family different from both `director` and `challenger` on
      both backends, asserted by a test over the model tables.
- [ ] A stub `dissent` verdict produces a blocking finding and triggers exactly one synthesis retry.
- [ ] A stub `dissent` with the retry budget exhausted reaches `done` with the dissent text present
      in `final_recommendation.md`.
- [ ] A `FinalRecommendation` with empty `limitations` produces exactly one
      `review.empty_limitations` finding.
- [ ] The rendered report contains a Limitations section listing unanswered issue-tree leaves.
- [ ] `tests/test_role_contracts.py` passes for both `reviewer-b.md` and the updated
      `synthesizer.md`.

## Verification plan

`make check`, `make frontend-check`, `uv run pytest tests/test_independent_review.py -v`, two stub
pipeline runs (concur and dissent), and one live `--budget-profile small` case confirming the
verdict appears in the Method room and the limitations in the delivered report.

## Verification results

**Verified 2026-08-04.**

Commands: `uv run ruff check`, `uv run ruff format --check`, `uv run mypy orchestrator`,
`uv run pytest` (792 passed, 18 deselected), `npm run typecheck`, `npm run check:clean`,
`npm test` (102 passed).

All acceptance criteria met except one, which the implementation proved unsatisfiable as written —
see below. `tests/test_independent_review.py` adds 17 tests, including the exclusion assertion that
is the point of the design: the packet is checked both by filename and by content, so the
pre-mortem narrative and the provisional rationale must appear nowhere in the projected text.

**One acceptance criterion could not be met as written, and the spec was wrong.**

The spec required `reviewer-b` to resolve to "a model family different from both `director` and
`challenger` on both backends". That is impossible: **only two model families are reachable on
either backend** — `xai`/`cursor-composer` on cursor, `openai`/`anthropic` on droid. A third does
not exist to configure.

Resolved by picking the binding constraint rather than pretending: north star Section 12 names
"recommendation synthesis and citation/calibration review" as a diversity boundary, and this role
re-derives the *Synthesizer's* conclusion. So the guarantee delivered — and asserted by
`validate_independent_review_family_diversity` plus a parametrized test over both backends — is
that `reviewer-b` never shares the **Synthesizer's** family. It does share the Director's on both
backends. That collision is mitigated structurally instead: the packet withholds every trace of the
Director's reasoning, which is the anchoring vector a shared family would otherwise amplify. The
mitigation is documented in the role yaml, the validator docstring and the model table.

**The `high_tier_calls` budget concern was a false alarm, and something more interesting sits
underneath it.** The spec flagged that `max_high_tier_calls` (6) might need raising. It does not:
the budget counts by *model*, not by declared role tier, and no model any role actually resolves to
maps to the high tier. On cursor every role runs on `low` models; on droid, `medium`. Seven roles
declare `model_tier: high` and not one of them consumes the high-tier counter.
**The cap is currently vestigial** — a guardrail that cannot fire on the shipped configuration.
That is not this spec's problem to fix, but it should be recorded: it means the escalation ladder's
cost ceiling is not being enforced by the mechanism that claims to enforce it. Added to ROADMAP
emergent work.

What the review does cost is one additional `agent_invocations` per case against a cap of 40. With
SPEC-040 and SPEC-042 also adding one each, the three together add three invocations; the first
real case used 45 against a raised cap. SPEC-044 must report invocation counts against the cap
rather than assuming headroom.

**Other deviations:**

1. **`IndependentReview` needed registering in `case_store.py` in four places**, not the two the
   spec implied — `_artifact_path` (write), `_artifact_path` (read by type), `_artifact_dir`, and
   the `list_artifacts` dispatch. Missing any one produces a `TypeError` or an `IsADirectoryError`
   rather than a clean failure.
2. **A third gate check** was added: `review.independent_reservations`, resolving the open question
   below.
3. **The invocation degrades rather than blocks.** A failed `reviewer-b` invocation audits
   `independent_review_skipped` and lets the case proceed without a second opinion. Dying at the
   last gate because the optional reviewer timed out would be worse than shipping without it, and
   the absence is visible in the audit trail rather than passing silently as a concur.
4. **`limitations` renders unconditionally**, with an explicit "no limitations were stated — treat
   that as an omission rather than a claim of completeness" line when the list is empty. A missing
   section would read as an absence of limitations.

## Open questions

None. The open question — whether `concur_with_reservations` blocks or is merely reported — was
resolved as proposed: a **non-blocking** `review.independent_reservations` finding, so it surfaces
in the integrity view without costing a synthesis retry. Covered by
`test_reservations_produce_a_non_blocking_finding`.
