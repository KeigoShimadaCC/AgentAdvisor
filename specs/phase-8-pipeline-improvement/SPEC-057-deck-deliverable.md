---
id: SPEC-057
title: Deck deliverable generated at case completion
phase: 8
status: verified
depends_on: []
parallel_with: []
north_star_refs: ["3", "5.6", "7.3", "9"]
last_updated: 2026-08-08
---

# SPEC-057 — Deck deliverable generated at case completion

## Summary

Turns the repo-local `consulting-deck` skill — today a manual, post-hoc tool run by hand under
`tmp/` — into a second deliverable tier the pipeline produces automatically. When a case reaches
`done`, the orchestrator deterministically renders the `FinalRecommendation` and its supporting
artifacts into a board-ready deck (editable PowerPoint, print PDF, per-slide PNGs) written into the
case directory, and exposes `advisor deck <case-id>` to regenerate it on demand. Deck generation is
best-effort and never able to turn a completed case into a failed one.

## Motivation

The pipeline's only deliverable is `outputs/final_recommendation.md`, and `advisor report` prints
that markdown. The professional-practice gap analysis (`report-and-findings/2026-08-04-consulting-practice-gap-analysis.md`)
catalogues this as gap 15, "one deliverable tier," and section 6 deferred it pending SPEC-042, which
is now `verified`. A single markdown document serves board-level and analyst-level readers alike;
consulting and think-tank practice tiers the deliverable — a board readout deck over the full
report — and that top tier is what a decision owner actually presents.

The `consulting-deck` skill already exists and already maps `FinalRecommendation` onto the standard
slide arc almost field for field (`.factory/skills/consulting-deck/case-mapping.md`). What is
missing is the wiring: the ROADMAP emergent-work entry of 2026-08-04 records exactly the three
questions this spec settles — where the deck artifact lives in the case directory, whether it is
gated on review passing, and whether matplotlib becomes a project dependency.

North star Section 3 promises an inspectable, auditable deliverable; the deck is a *view* of the
already-validated artifacts, so it inherits that auditability only if it is generated from those
files rather than retyped. Sections 5.6 and 9 make the four uncertainty measures — outcome
probability, evidence confidence, recommendation confidence and model stability — four distinct
quantities that must never be merged; the deck template must preserve that separation, which is the
single place a summary slide most often violates it.

## Scope

- `orchestrator/deck.py` — deterministic deck generator:
  - `build_deck(case, *, present=False) -> DeckResult` — reads artifacts through the typed
    `case.read_artifact(...)` / `case.list_artifacts(...)` API rather than hardcoded YAML paths
    (see the path note in Design), emits `slides.html` into the case's deck directory by filling a
    fixed template, then invokes the skill's `build_deck.py --name deck --out-dir <deck-dir>` and
    (best effort) `render_deck.mjs <deck-dir>/deck.preview.html --out <deck-dir>` as subprocesses.
  - `DeckResult` — a dataclass recording which artifacts were produced (`html`, `pptx`, `pdf`,
    `pngs`), the geometry `report.json` summary, and any degradations (`charts`, `render`) with
    their reasons.
  - `generate_deck_for_case(case) -> DeckResult | None` — the non-fatal wrapper the pipeline calls;
    swallows and audits every exception, emitting one of `deck_generated`,
    `deck_generation_degraded` (a tier was skipped) or `deck_generation_failed`.
- `orchestrator/deck_template.py` — the field-to-slide mapping from `case-mapping.md`, expressed as
  pure functions from artifacts to HTML fragments using only the classes in `design-system.md`. No
  agent invocation; action titles are composed deterministically from recommendation fields.
- `orchestrator/deck_charts.py` — chart generation (scenario bars, outcome-probability bar) reading
  the same artifacts, guarded so that absence of matplotlib degrades to HTML/CSS table exhibits
  rather than failing.
- `orchestrator/pipeline.py::run` — after the existing `_record_into_memory` call, when
  `final_state.stage is CaseStage.DONE`, call `generate_deck_for_case(case)`.
- `orchestrator/cli.py` — `advisor deck <case-id> [--present]`, producing or regenerating the deck
  for a completed case and printing the artifact paths. `cmd_deck(args, backend)` follows the
  read-only-command convention and `del backend`s it, since generation calls no model. (An `--open`
  convenience flag was dropped as out of scope; the command prints the paths instead.)
- `orchestrator/service/lexicon_data.yaml` — narration entries for `deck_generated`,
  `deck_generation_degraded` and `deck_generation_failed`. Both `tests/test_lexicon.py` and
  `tests/test_lexicon_coverage.py` auto-discover `event_type=` literals in `orchestrator/` and
  fail if any lacks an entry, so these three are mandatory, not optional.
- `pyproject.toml` — a new optional `deck` dependency group carrying `matplotlib` (see the
  dependency note in Design; this is the one item needing user sign-off under AGENTS.md).
- `.gitignore` — the in-case deck directory is already covered by `cases/*`; no change expected,
  confirmed by a test.
- `tests/test_deck.py` — unit tests over the fixture case; a stub-pipeline assertion that the deck
  directory appears at `done`; a degradation test with the render toolchain forced absent.

## Out of scope

- **Any change to case lifecycle or the state machine.** The deck is produced at `done` and the case
  stays terminal, exactly as SPEC-042 established for monitoring. No `DECK` stage, no new transition.
- **An agent-authored deck.** No new role, no backend invocation, no budget consumption. The deck is
  a deterministic projection; wording is refined by the user in the editable PowerPoint, not by a
  model at runtime.
- **The aesthetic visual-QA loop.** The skill's human "read the PNGs" pass is not automated. The
  deterministic generator relies on the geometry report (`report.json`) to gate layout defects;
  taste is left to the user editing the `.pptx`.
- **Binary chart formats beyond PNG, remote assets, or themes/branding controls.** Reading-deck
  scale only; `--present` toggles the skill's existing presentation scale.
- **Shipping the deck through the web UI or the service beyond a download path.** A Delivery-screen
  surface can follow in Phase 9; this spec stops at files on disk and the CLI.

## Design

**Deterministic generation, not an agent.** AGENTS.md orders decision quality and determinism above
all else, and the case-mapping is already close to mechanical. `deck_template.py` fills a fixed
template from `FinalRecommendation` and its neighbours: the executive-summary action title is
composed from `recommended_action` and `timing`; each key reason becomes a card carrying its
`[E-]`/`[A-]` markers; `alternatives_considered` becomes a ranked table with the recommended row
highlighted; `scenario_analysis` and `outcome_probabilities` drive the charts; the four uncertainty
measures each get their own KPI with its `basis` string beneath. Determinism buys reproducibility
(the same case always yields the same deck), zero token cost, and no LLM variance in a board
artifact — at the price of templated rather than hand-crafted action titles, which the editable
export lets the user sharpen.

**The hook mirrors `_record_into_memory`.** In `pipeline.run`, deck generation runs in the same
`final_state.stage is CaseStage.DONE` block, immediately after the memory snapshot, wrapped so that
any failure emits an audit event and returns `None`. A completed, delivered case must never be
downgraded to `failed` because Chromium was missing or a chart script raised. This is the same
degradation contract memory recording already follows.

**The hook fires in both interactive and unattended runs — verified against the code.** Every path
that transitions a case to `done` passes through `pipeline.run`: the unattended path
(`auto_approve=True` → `_run_unattended`) returns to `run` at `done`, and the interactive path is
`advisor approve` at the final gate → `cli._run` → `run_pipeline(..., auto_approve=False)`, which
runs the state machine from `AWAITING_FINAL_APPROVAL` to `done` and then reaches the same block.
So "automatic at the end of every completed case" needs no new call site beyond this one hook.

**Layered toolchain, graceful degradation.** The generator produces the most valuable artifacts
with the fewest dependencies and degrades from there:

1. `slides.html` (the authored source) plus the editable `deck.pptx.html` and the intermediate
   `deck.preview.html` come from `build_deck.py`, which is standard-library-only Python (verified:
   it imports `argparse`, `base64`, `mimetypes`, `re`, `sys`, `pathlib` and nothing else) and is
   always available. This is the tier that must always succeed. Note `build_deck.py` does not emit
   the PDF — that is the render tier below.
2. Chart PNGs need matplotlib. If it is importable, charts render; if not, `deck_charts.py` emits the
   same figures as HTML/CSS `.tbl` exhibits and records `charts: degraded`. (The demo deck already
   used a table exhibit for the valuation slide, so this fallback is proven to read well.)
3. `deck.pdf`, the per-slide PNGs and the geometry `report.json` come from `render_deck.mjs`, which
   needs Node plus the Playwright Chromium that `frontend/` installs — it calls `loadChromium()`
   over `playwright`/`@playwright/test`/`playwright-core`. If `node` is not on `PATH`, or Playwright
   is not installed, or the render exits non-zero, that tier is skipped and recorded as
   `render: skipped`, leaving the HTML and PowerPoint intact.

`DeckResult` reports exactly which tiers ran, so `advisor deck` can tell the user what they got and
why anything is missing. Because the geometry `report.json` only exists when tier 3 runs, the
zero-errors acceptance criterion below is conditional on the render toolchain being present.

**The dependency decision.** matplotlib is not a project dependency and the skill invokes it today
via `uv run --with matplotlib`, which is fine for a hand-run tool but wrong for an in-process
pipeline step (it shells out and can hit the network). The proposal is a new optional
`[dependency-groups] deck = ["matplotlib"]` group: additive, off the default install path, and
required only by whoever wants chart PNGs. Because chart generation degrades to table exhibits when
matplotlib is absent, a default install still produces a complete deck. Adding any dependency needs
user sign-off per AGENTS.md, so this is the spec's one open decision (see Open questions).

**Artifact location and read path.** The deck is written to `cases/<case-id>/outputs/deck/`:
`slides.html`, `deck.preview.html`, `deck.pptx.html`, and — when the render tier runs — `deck.pdf`,
`slide-01.png …`, `report.json`. It sits beside `final_recommendation.md` under the
already-gitignored `cases/*`. The inputs are read through the typed `case.read_artifact` /
`case.list_artifacts` API, not raw paths: this matters because `final_recommendation.yaml` is the
one artifact the pipeline writes under `outputs/`, while everything else (`decision_spec`,
`evidence/`, `assumptions/`, `premortem_report`, …) is under `shared/`. `case-mapping.md` had this
wrong — it pointed at `shared/final_recommendation.yaml`, which is the bug that surfaced when the
demo deck was built by hand — and this spec corrects that table as part of its deliverables.

**Regeneration.** Text files are written through the existing `case_store.atomic_write_text` helper,
which writes to a temp file and `os.replace`s it, so no individual file is ever half-written. The
deck directory itself is not swapped atomically (POSIX `os.replace` cannot replace a non-empty
directory); instead `build_deck` clears and rewrites `outputs/deck/` on each run. This is safe
because the deck is a derived, regenerable artifact — no reader depends on it mid-write, and a
failed rerun leaves the previous files replaced file-by-file rather than corrupting a load-bearing
case artifact.

**Not gated on review.** The deck is a projection of the `FinalRecommendation`, which only exists
once synthesis and review have passed and the case has reached `done` through the final approval
gate. Generating after `done` therefore means the deck can only ever reflect approved content; no
new gate is required, and none is added.

**Uncertainty separation is a hard invariant.** `deck_template.py` renders the four measures as four
KPIs with distinct labels and prints each `basis`; `model_stability` is rendered as
`runs_supporting/runs_total`, never a percentage. A test asserts four distinct measure figures are
present and that model stability is not formatted as a percentage, so a future template edit cannot
silently collapse them.

## Deliverables

- [x] `orchestrator/deck.py` — `build_deck`, `generate_deck_for_case`, `DeckResult`
- [x] `orchestrator/deck_template.py` — artifact-to-HTML mapping per `case-mapping.md`
- [x] `orchestrator/deck_charts.py` — charts with table-exhibit fallback
- [x] `orchestrator/pipeline.py` — non-fatal deck hook in the `DONE` block
- [x] `orchestrator/cli.py` — `advisor deck <case-id> [--present]`
- [x] `pyproject.toml` — optional `deck` dependency group (matplotlib; signed off)
- [x] `orchestrator/service/lexicon_data.yaml` — narration for `deck_generated`,
      `deck_generation_degraded`, `deck_generation_failed`
- [x] `.factory/skills/consulting-deck/case-mapping.md` — corrected the final-recommendation path
      from `shared/` to `outputs/` (done in this spec's audit pass)
- [x] `tests/test_deck.py` (10 tests) plus a deck assertion added to
      `tests/test_pipeline_stub.py::test_pipeline_stub_e2e`

## Acceptance criteria

- [x] `make check` is green.
- [x] `advisor deck case-001-fixture-001` produces `outputs/deck/slides.html` and
      `outputs/deck/deck.pptx.html`, and prints their paths.
- [x] Building the deck for the fixture case yields a geometry `report.json` with zero errors when
      the render toolchain is present.
- [x] The deck renders the four uncertainty measures as four distinct figures, and `model_stability`
      as `runs_supporting/runs_total`, asserted by a test over the generated HTML.
- [x] Every `[E-]`/`[A-]` citation marker in the recommendation text that reaches a slide resolves
      in the evidence/assumption appendix, asserted by a test.
- [x] With matplotlib forced unimportable, deck generation still produces `slides.html` and
      `deck.pptx.html`, and `DeckResult` records `charts: degraded`.
- [x] With `node` forced off `PATH`, deck generation still produces the HTML and PowerPoint, and
      `DeckResult` records `render: skipped`; no exception propagates.
- [x] A stub pipeline run that reaches `done` leaves `outputs/deck/` populated, and an injected deck
      failure leaves the case at `done` (not `failed`) with a `deck_generation_failed` audit event.
- [x] The delivered case's stage history is unchanged from the pre-change pipeline.
- [x] No audit event emitted by this spec renders through the lexicon's unknown-event fallback,
      asserted by `tests/test_lexicon.py` and `tests/test_lexicon_coverage.py` (both already scan
      `orchestrator/` for `event_type=` literals; the three deck events must have entries).

## Verification plan

`make check`; `uv run pytest tests/test_deck.py -v`; `advisor deck case-001-fixture-001` followed by
opening the resulting `deck.pdf` and confirming the page count matches the slide count; a stub
pipeline run asserting `outputs/deck/` exists at `done`; two degradation runs with matplotlib and
then `node` forced absent; and a diff of the case directory's `state.yaml` and audit stage history
before and after generation to confirm the case stays terminal.

## Verification results

Executed 2026-08-08. All acceptance criteria pass.

- **`make check` green.** `ruff check` and `ruff format --check` pass across `orchestrator tests
  scripts` (deck HTML template carries a scoped `per-file-ignores` for `E501`, since its lines are
  authored markup); `mypy orchestrator` reports "no issues found in 79 source files"; the full
  `uv run pytest` suite is **938 passed, 19 deselected** in ~106s.
- **`tests/test_deck.py` — 10 tests, all pass** (`uv run pytest tests/test_deck.py -v`): tier-1
  always succeeds; `FinalRecommendation` required (else `DeckError`); chart image used when
  available and table exhibit otherwise; four distinct uncertainty measures with `model_stability`
  rendered `0/1` and never as a percentage; every `[E-]`/`[A-]` marker resolves to an appendix row;
  charts degradation recorded; `generate_deck_for_case` non-fatal on failure with a
  `deck_generation_failed` audit; success audits `deck_generated`/`deck_generation_degraded`; the
  three lexicon entries exist.
- **CLI on the fixture.** `advisor deck case-001-fixture-001` prints the PowerPoint, PDF, slides and
  image paths. With the render toolchain present the geometry `report.json` reports
  `slides: 11, errors: 0` (one `advice`-level underfull finding on the change-triggers slide, which
  carries a single trigger in this fixture — advisory, not an error). With the optional `deck` group
  installed, `charts/scenarios.png` renders (base case highlighted) and there are no degradations;
  without matplotlib, the run degrades to the table exhibit and records `charts` skipped.
- **Automatic hook e2e.** `tests/test_pipeline_stub.py::test_pipeline_stub_e2e` now asserts a stub
  run reaching `DONE` leaves `outputs/deck/slides.html` and `outputs/deck/deck.pptx.html` on disk
  and audits `deck_generated`/`deck_generation_degraded`. The case stays at `DONE`; stage history is
  unchanged (the hook only appends artifacts and audit lines after `_record_into_memory`).

## Open questions

None. matplotlib was signed off as the optional `[dependency-groups] deck` group; chart generation
degrades to HTML/CSS table exhibits when it is absent, so a default install still builds a complete
deck.
