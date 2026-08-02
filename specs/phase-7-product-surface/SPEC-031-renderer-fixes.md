---
id: SPEC-031
title: Renderer and presentation-data fixes
phase: 7
status: verified
depends_on: [SPEC-018]
parallel_with: [SPEC-027, SPEC-028, SPEC-029]
north_star_refs: ["9", "10", "16"]
last_updated: 2026-08-03
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

- [x] `orchestrator/artifacts/sentinels.py` (placeholder predicates)
- [x] renderer: per-bullet citation fix, sentinel rendering, pre-mortem section, group labels
- [x] normalize: origin-keyed `independence_group` + `humanize_independence_group`
- [x] gate check `synthesis.missing_critical_assumptions` + synthesizer md amendment
- [x] thesis digest word-boundary truncation
- [x] tests: `tests/test_sentinels.py` (new) plus additions to `test_render.py`,
      `test_normalize.py`, `test_gates.py`, `test_thesis.py`

## Acceptance criteria

- [x] Rendering the reference final-recommendation fixture yields no bullet carrying the full
      shared citation list (assert a known key-reason line contains exactly its own inline ids);
      the evidence table is unchanged.
- [x] A fixture with `runs_total: 1` renders "not assessed" and no "0.0%" anywhere in the
      stability line; a coercion-basis confidence renders without a percentage.
- [x] A case with a `premortem_report.yaml` renders a "## Pre-mortem" section containing every
      failure mode and the most-likely marker; absent report → absent section.
- [x] Two evidence records from the same publisher answering different questions normalize into
      one `independence_group` (unit), and the rendered table shows the human label.
- [x] The new gate warns when the ledger is populated and `critical_assumptions` is empty, and
      stays silent when ids are present. *(Amended: the committed reference fixture has
      `critical_assumptions: [A-001]` and is shared with `test_role_synthesis.py`, so the warn
      case is constructed in-test rather than by editing that fixture.)*
- [x] `make check` passes.

## Verification plan

```
uv run pytest tests/test_render.py tests/test_normalize.py tests/test_gates.py tests/test_thesis.py -q
make check
```

## Verification results

**2026-08-03.** `make check` green: ruff, ruff format, mypy on 63 source files, 603 unit tests
(17 live deselected). Sentinel predicates additionally spot-checked outside the suite against
live `ModelStability` / `ConfidenceAssessment` values: `runs_total=1` and the coercion basis
return True, a 16/20 stability and a real basis return False.

Judgement calls made during implementation, recorded because they differ from a literal reading
of the spec:

- **Sentinel strings are imported, not copied.** `sentinels.py` imports `_DEFAULT_FILLERS`,
  `_CONFIDENCE_WORD_VALUES` and `_confidence_from_word` from `yaml_io.py` — private names, on
  purpose. A second copy of the filler literals would drift, and a drifted sentinel fails
  silently by re-labelling a placeholder as a measurement. `tests/test_sentinels.py` drives the
  real coercion entry points so a `yaml_io` change breaks the test rather than the product.
- **Human independence labels are best-effort for ids this code never minted.**
  `humanize_independence_group` labels any id carrying a kind marker, including legacy
  question-prefixed ones, but passes through markerless ids (the fixture's `aaa-q2-filing`)
  rather than inventing a label — which is also what keeps the reference evidence table
  byte-identical.
- **Sentinel lines keep the `[calculation]` provenance label.** The text says "not assessed",
  but the bullet was not re-labelled, so the six-label lexicon SPEC-032/033 key off stays
  stable.
- **The pre-mortem section omits referenced evidence/assumption ids**, which are not guaranteed
  to appear in the recommendation's evidence table and would render as dangling references.
- The render golden `tests/fixtures/roles/synthesis/replay/final_recommendation.md` was
  regenerated: 8 bullets lost their appended citation spam. Byte-identity is still asserted, now
  against the corrected golden, and the evidence-table rows are unchanged. No test was weakened
  or deleted.

## Open questions

- None.
