---
id: SPEC-031
title: Renderer and presentation-data fixes
phase: 7
status: draft
depends_on: [SPEC-018]
parallel_with: [SPEC-027, SPEC-028, SPEC-029]
north_star_refs: ["9", "10", "16"]
last_updated: 2026-08-02
---

# SPEC-031 — Renderer and presentation-data fixes

## Summary

Fixes the defects that make the current user-facing output misleading or unreadable, all observed
in the completed reference case: the renderer appends the entire case citation list to every
bullet (~40% of the document is duplicated citation noise); coercion placeholders render as
measurements ("Model stability: 0.0% (0/1 sensitivity runs)"); the pre-mortem never reaches the
report; `critical_assumptions` arrives empty despite a populated ledger; `independence_group`
keys embed the research question (understating source concentration) and leak raw slugs into the
citation table; thesis `rationale_digest` strings truncate mid-word.

## Motivation

North star Section 16 defines the report as the product's face; Section 9 forbids presenting one
uncertainty quantity as another — a placeholder rendered as a measurement is the same defect.
Section 10 makes independence accounting a core promise. These fixes serve both the Markdown
export and the CaseView projection (SPEC-032), which must not have to work around them.

## Scope

- `orchestrator/render.py`:
  - stop appending `_citation_suffix(shared_citations)` to individual bullets; render only the
    model-supplied inline citations per line, keep one consolidated reference list plus the
    evidence table in "Evidence and citations".
  - sentinel-aware rendering: `ModelStability` with `runs_total <= 1` renders as
    "Model stability: not assessed (single run)"; a `ConfidenceAssessment` whose basis is the
    coercion default ("Not independently assessed", or a recorded word-substitution basis)
    renders the basis text without a percentage. Sentinel predicates live in one module
    (`orchestrator/artifacts/sentinels.py`) shared with SPEC-032.
  - new "## Pre-mortem" section (after "Strongest counterarguments"): assumed outcome, failure
    modes with probability/severity, leading indicators, most-likely flag — rendered from
    `premortem_report.yaml` when present.
  - independence groups render as human labels (see below), never raw slugs.
- `orchestrator/normalize.py`: `independence_group` assignment keys on origin (registrable
  publisher/domain), not question+publisher, so the same origin across two research questions
  forms one group. Existing recorded groups are not migrated; the evidence critic consumes
  whatever is on disk.
- `orchestrator/gates.py`: new WARN check `synthesis.missing_critical_assumptions` — fires when
  the ledger holds high-materiality assumptions but `FinalRecommendation.critical_assumptions`
  is empty (root cause is synthesizer behavior; the gate makes the omission loud instead of
  silent).
- `cursor/roles/synthesizer.md`: explicit instruction + example that `critical_assumptions` must
  list the load-bearing `A-` ids from the provided ledger.
- `orchestrator/thesis.py`: digest truncation at a word boundary with an ellipsis.

## Out of scope

- Any change to artifact schemas or the four uncertainty measures themselves.
- Re-scoring or migrating existing cases' independence groups.
- The interactive brief's own rendering (SPEC-035 renders from structured data; this spec fixes
  the canonical export and the data both consume).
- Live citation re-fetching (north star open question 8).

## Design

Rendering stays deterministic and total: every branch that previously printed a number now has an
explicit not-assessed branch, so the export and the UI can never disagree about what was
measured. The sentinel predicates are the single source of truth for "this value is a
placeholder" — SPEC-032 imports them rather than re-deriving. The independence key change is a
normalization-time policy, deliberately upstream of the critic so `max_cluster_share` becomes
honest without touching its math.

## Deliverables

- [ ] `orchestrator/artifacts/sentinels.py` (placeholder predicates)
- [ ] renderer: per-bullet citation fix, sentinel rendering, pre-mortem section, group labels
- [ ] normalize: origin-keyed `independence_group`
- [ ] gate check `synthesis.missing_critical_assumptions` + synthesizer md amendment
- [ ] thesis digest word-boundary truncation
- [ ] tests: `tests/test_render.py` additions, `tests/test_normalize.py` additions,
      `tests/test_gates.py` addition

## Acceptance criteria

- [ ] Rendering the reference final-recommendation fixture yields no bullet carrying the full
      shared citation list (assert a known key-reason line contains exactly its own inline ids);
      the evidence table is unchanged.
- [ ] A fixture with `runs_total: 1` renders "not assessed" and no "0.0%" anywhere in the
      stability line; a coercion-basis confidence renders without a percentage.
- [ ] A case with a `premortem_report.yaml` renders a "## Pre-mortem" section containing every
      failure mode and the most-likely marker; absent report → absent section.
- [ ] Two evidence records from the same publisher answering different questions normalize into
      one `independence_group` (unit), and the rendered table shows the human label.
- [ ] The new gate warns on the reference fixture (ledger populated, `critical_assumptions`
      empty) and stays silent when ids are present.
- [ ] `make check` passes.

## Verification plan

```
uv run pytest tests/test_render.py tests/test_normalize.py tests/test_gates.py tests/test_thesis.py -q
make check
```

## Verification results

—

## Open questions

- None.
