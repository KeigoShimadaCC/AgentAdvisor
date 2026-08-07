# Phase 9 — UX Improvement

**Status:** all twelve sheets written and `draft`; none approved. This document is the plan and the rationale; the sheets are the contract.
**Spec range:** SPEC-045 → SPEC-056 (12 specs). SPEC-038–044 are phase 8 (pipeline improvement), merged and `verified`.
**Source:** the UX review at `report-and-findings/2026-08-04-ux-review.md` (11 areas, 19 sequenced recommendations),
reconciled against phase 8 at `d179f2b`, then re-checked against the merged phase 8 at `f8f0ce4`.

> ### Phase 8's outputs: four of seven still have no screen
>
> **Corrected 2026-08-05, when phase 8 merged.** The original claim here — that none of SPEC-038–044
> reaches the UI — was read off the *spec sheets*, where the frontend is indeed never mentioned. The
> implementation did more than its sheets: phase 8 shipped ~900 lines of frontend across Delivery,
> the scope checkpoint and the interview cards. Stating it as "seven invisible features" was wrong,
> and the PR that said so overstated it.
>
> Measured against the merged tree rather than the sheets:
>
> | Phase 8 output | In `CaseView` | On a screen |
> |---|---|---|
> | Objective weights and computed ranking | yes | **yes** |
> | Typed action plan (`NextAction`) | yes | **yes** |
> | Limitations / "what could not be assessed" | yes | **yes** |
> | Independent review verdict | yes | no |
> | Diagnosticity (ACH) matrix | yes | no |
> | Monitoring plan and risk register | no | no |
> | Private evidence provenance (`user_document`) | no | no |
>
> So SPEC-053 shrinks rather than disappears: two outputs need rendering only, two need projection
> *and* rendering, and three are done. The underlying risk was real — the `calibration.py` pattern of
> building something fully and never surfacing it — but it applies to four items, not seven, and
> `coverage.spec.ts` remains the mechanism that stops it recurring.
>
> **Note (2026-08-07, merge with main).** The 2026-08-06 spec sweep on `main` reached the same
> conclusion independently and added its own ACH panel to the Options room, so merging phase 9 into
> main briefly rendered the matrix twice. The two were reconciled into the single
> `DiagnosticityMatrix` component this table's "Diagnosticity (ACH) matrix" row refers to, which
> keeps the sweep's rank filtering and empty-table guard alongside SPEC-053's eliminated-row marking
> and overflow handling.

## Why this phase exists

Phase 7 shipped the product surface and verified it end to end. It works. What it does not yet do is
communicate — and §15 of the north star already says what it should:

> *"agents work while the interface exposes meaningful progress rather than raw chain-of-thought"*
> *"the interface should distinguish clearly between sourced facts, agent interpretation,
> user-supplied information, assumptions, calculations, and recommendations"*

Phase 9 is therefore not new product scope. It is closing the gap between the shipped surface and
§15, which was written before there was a UI to hold it to.

## The binding constraint

**The pipeline flow does not change.** No stage, no transition, no handler, no role, no artifact
schema is modified by phase 9. Reconciling against phase 8 made this *stronger* — phase 9 no longer
adds any artifact type at all:

| Addition | Spec | Kind |
|---|---|---|
| `role_invocation_started`, `role_invocation_progress` audit events + 2 lexicon rows | 046 | additive |
| `new_case` returns before the worker halts (uses the existing `spawn_worker_background`) | 046 | control-layer |
| `needs_you` on the case-list endpoint | 046 | additive field |
| `GET /api/calibration` over the existing `MemoryStore.calibration()` | 046 | additive read |
| `GET /api/effort-history` — p50–p90 ranges per effort profile over `prior_cases()` | 046 | additive read |
| `CaseView` projection extended to carry phase 8's artifacts | 053 | additive read model |

Every entry is a read or an emit. `caseview.py` is a projection built from disk, so extending it
touches no stage, transition or handler. SPEC-046 carries a regression test asserting zero diff in
`state_machine.py` transitions and handlers, so "the pipeline did not change" is a checkable claim
rather than a promise.

**Dropped after reconciliation.** Phase 9 originally planned a user-note artifact so people could
add context mid-run. **Phase 8 SPEC-043 builds a better version of that** — a private evidence
channel taking files from `cases/<case-id>/inputs/` plus open substantive intake questions,
producing proper evidence records with `source_type: user_document` and correct isolation from the
review roles. Phase 9 drops its own note channel and renders phase 8's instead. Likewise, phase 9
planned to build the outcome loop; **SPEC-042 already closes it** into the existing Brier machinery,
so phase 9 renders rather than rebuilds.

---

## Reconciliation with phase 8

Every phase 8 spec produces something a user should see. None of the *sheets* says who renders it;
the implementation rendered three of the seven anyway. The rows below are the plan as written, with
the post-merge status added.

| Phase 8 spec | Produces | Phase 9 impact |
|---|---|---|
| 038 value-model binding | Objective weights **elicited at the scope checkpoint**; deterministic ranking; a gate finding when computed and stated rank disagree | Direct collision with **050**, which redesigns that sheet. 050 builds an extension slot; **053** fills it. Rank disagreement is a new thing the UI must be able to show. |
| 039 independent review + limitations | A reviewer on a **third** model family whose dissent **blocks delivery**; an explicit "what could not be assessed" statement | **049** must treat dissent as three-voiced, not two. The limitations statement is a new delivery element (**053**). |
| 040 competing hypotheses | A diagnosticity matrix: evidence × alternatives, ranked by *disconfirming* evidence | A substantial new UI object with no home in the original plan. Goes to **053**, surfaced through **048**'s context panel. |
| 041 typed action plan | `NextAction` with owner, date, first step, cost, dependencies, urgency | Replaces the current `next_actions` string list on delivery. **050** leaves a slot; **053** fills it. |
| 042 monitoring + post-delivery | Monitoring plan, risk register, `advisor watch`, closes the loop into Brier calibration | Supersedes phase 9 *building* the outcome loop. SPEC-042 shipped its own Delivery-screen block and read endpoint; **053** owns the full monitoring surface and a screen for the CLI-only `advisor watch`; **051** drives the notification side (due-check nudges on the watch-or-notify preference). *(Corrected 2026-08-06: this row previously said 051 renders it, which 051's own sheet disclaims.)* |
| 043 private evidence channel | User files in `cases/<id>/inputs/`; open intake questions; `source_type: user_document` | Supersedes phase 9's note channel entirely. **049** must render this provenance as its own voice — §15 requires distinguishing user-supplied information from agent interpretation. |
| 044 phase 8 re-evaluation | Measurement of phase 8 | None. |

**File-level conflicts, as actually observed on merge.** The prediction that phase 8 touched none of
`styles.css`, `useCaseView`, `SSEClient` or the service endpoints was half right: it left the stream
and the projection loader alone, but it did change `styles.css`, `app.py`, `schema_export.py` and the
Playwright config. Merging cost four conflicts, all resolved additively, and the two guards SPEC-045
and SPEC-046 introduced both fired on real drift — phase 8's new CSS referenced four token names the
migration had removed, and its new pipeline stage tripped the invariants snapshot. That is the
guards working, not a problem, but "no file-level conflict" was the wrong prediction and is corrected
here.

Only SPEC-053 hard-depends on phase 8 being verified — the dependency risk is deliberately isolated
in one spec so a phase 8 slip blocks one sheet rather than three.

## Sizing: why 12 and not 17

A first pass at this plan proposed 17 specs. Measuring the existing sheets showed that was roughly
2.5× too fragmented for this repo's conventions.

| Metric across phases 6–7 (15 specs) | Range |
|---|---|
| Lines per sheet | 104–192 (median ~125) |
| Deliverables per sheet | 3–6 (typically 5–6) |
| Acceptance criteria per sheet | 3–7 (typically 6) |

Breadth matters more than the counts. **SPEC-035 alone** covers the entire Brief route (skeleton,
live assembly with settle animation, margin narration, working-view card, method strip, sealed
answer card), the entire Delivery sheet (answer card, all four uncertainty widgets, integrity slip,
full brief with provenance, signature, export, print stylesheet), the Notification API with
permission handling and an in-app fallback, and three failure-path renderings — in 141 lines, 6
deliverables, 7 acceptance criteria.

Six of the 17 proposed specs fitted inside that single sheet's footprint. Phase 7 delivered the
whole web product in 11 specs, so nine was the proportionate number for the review's own findings.
Three sheets were then added for work the compression did not cover — SPEC-053 for phase 8's
rendering, and SPEC-054 and SPEC-055 for two gaps found by auditing the drafted sheets back against
the discussion (see Audit below). Twelve is the result: fewer sheets than the first plan, more work
than it covered.

Compression applied:

Named rather than numbered, because the first plan's numbering no longer maps onto the sheets that
exist:

| Sheets in the first plan | Merged into | Why |
|---|---|---|
| stream + narrator + case map | **SPEC-047** | All three are "the interface says what is actually happening" |
| shell + document + altitudes | **SPEC-048** | All three restructure the same surfaces; directly analogous to SPEC-035's breadth |
| commissioning + checkpoints | **SPEC-050** | The three human moments: create, scope, sign |
| presence + engagement + calibration screen | **SPEC-051** | Everything about the user when they are not reading |
| share/replay + library/mobile | **SPEC-052** | Reach and distribution |

SPEC-048 is the largest and the natural split point if implementation shows it does not fit one
session. `specs/README.md` already sanctions that: *"If implementation reveals the spec is wrong,
update the spec first."*

---

## Frontend testing

### What already exists and will be reused

The existing frontend test infrastructure is stronger than the review credited, and several things
phase 9 might have proposed as new are already built:

- **Unit/component:** Vitest + jsdom + `@testing-library/react` + `user-event` + `jest-dom`.
  77 tests. `make frontend-check` runs tsc, the type-generation drift check, and the suite.
- **E2E:** Playwright with three deterministic backing modes — `fixture` (committed dummy cases),
  `stub` (real orchestrator on StubBackend, full lifecycle asserting DOM *and* disk state at every
  gate), `replay` (recorded audit timing). Dedicated non-dev ports. `make e2e-frontend`.
- **Accessibility:** `@axe-core/playwright` on 6 screens at wcag2a/aa + wcag21a/aa, zero
  serious/critical.
- **Terminology guard:** already sweeps 5 screens for raw enum strings. Phase 9 extends it rather
  than inventing it.
- **Schema drift:** `npm run check:clean` fails if generated types drift from the JSON schemas.

### What is genuinely missing — and lands in SPEC-045

For a phase whose subject is visual, these gaps are the ones that matter:

1. **No visual regression of any kind.** Playwright is present; `toHaveScreenshot` is never used.
   Nothing today can detect an unintended layout or color change.
2. **No theme testing.** SPEC-037's acceptance criterion *"Axe passes on the six covered screens in
   both themes"* is checked, but there is one theme and no `colorScheme` handling anywhere in `e2e/`.
3. **No responsive testing.** Both Playwright projects are desktop (`Desktop Chrome`,
   `Desktop Safari`). No mobile viewport is ever exercised. *(Partially closed 2026-08-06: a
   `mobile` project at 390×844 now runs the library and scope-checkpoint flows in fixture mode.
   The rooms and the brief remain unexercised at that width — that coverage is SPEC-052's.)*
4. **No reduced-motion test**, though both `styles.css` and `Brief.tsx` branch on it.
5. **No contrast assertions** on color pairs.
6. **Axe covers 6 of ~13 routes.** The plan, method, options and assumptions rooms and the inspector
   are untested.

### The per-spec testing contract

Every phase 9 spec sheet must carry all six of these in its acceptance criteria — this is the
standard the sheets will be written against, not a per-spec choice:

1. **Unit tests** for pure logic (reducers, selectors, formatters) — testable without a DOM.
2. **Component tests** via Testing Library for each new or changed component.
3. **At least one e2e assertion** in whichever of fixture/stub/replay mode fits the behaviour.
4. **Axe clean** on every screen the spec touches, **in both themes**, with the spec's screens added
   to the axe list.
5. **Visual-regression baselines** for every screen the spec touches, across the theme × viewport
   matrix, with baseline changes reviewed in the diff rather than blind-accepted.
6. **Terminology guard extended** to any new screen.

---

## Sheets

Written 2026-08-05, all `draft`, none approved. Each is 122–143 lines with 6–7 deliverables
and 7–8 acceptance criteria. *(Ranges corrected 2026-08-06 against the sheets as written; the
earlier "118–140 lines, 6 deliverables, 7 criteria" was the calibration target, not the
measured result.)*

| Spec | Title |
|---|---|
| [SPEC-045](SPEC-045-design-system-and-visual-regression.md) | Design system — tokens, type scale, theming, and the visual-regression harness |
| [SPEC-046](SPEC-046-service-additions.md) | Service additions — progress events, non-blocking creation, projection reads |
| [SPEC-047](SPEC-047-live-case-narrator-and-map.md) | The live case — streaming truth, the narrator, and the case map |
| [SPEC-048](SPEC-048-reading-room.md) | The reading room — shell, persistent chrome, hierarchy, and altitudes |
| [SPEC-049](SPEC-049-the-cast.md) | The cast — voice attribution, margin objections, and dissent |
| [SPEC-050](SPEC-050-commissioning-and-checkpoints.md) | Commissioning and checkpoints — the first five minutes and the two signatures |
| [SPEC-051](SPEC-051-presence-and-engagement.md) | Presence and engagement — notifications, the away digest, reactions, calibration |
| [SPEC-052](SPEC-052-distribution.md) | Distribution — export, share, replay onboarding, the library workspace, and mobile |
| [SPEC-053](SPEC-053-phase-8-made-visible.md) | Phase 8 made visible — projecting and rendering the pipeline improvements |
| [SPEC-054](SPEC-054-calibration-language.md) | The calibration language — one uncertainty vocabulary at every altitude |
| [SPEC-055](SPEC-055-resilience-and-budgets.md) | Resilience — degraded states, storage failure, live-region announcement, and budgets |
| [SPEC-056](SPEC-056-phase-9-reevaluation.md) | Phase 9 re-evaluation — visual regression, full e2e, and a real case on the new surface |

## Sequencing

Six waves. Waves are sequential; within a wave, specs run in parallel where the sheets declare
`parallel_with`. *(Corrected 2026-08-06: this said "four waves" while listing six, and claimed
every intra-wave pair was `parallel_with`. The sheets say otherwise and the sheets are the
contract: wave B is internally ordered — 048 `depends_on` 047, the narrator stream before the
shell that hosts it — and in waves C and D the declared pairs are 049∥050∥054 and 051∥052∥055.
The reciprocal declarations were symmetrised the same day: 049 now lists 054 and 052 lists 055.)*

| Wave | Specs | Job | Phase 8 dependency |
|---|---|---|---|
| A — Foundation | 045, 046 | Design system + test harness; the backend additions | none — can start now |
| B — Truth and form | 047 → 048 | Say what is happening; rank the information | none |
| C — Substance | 049, 050, 054 | The deliberation; the human moments; the uncertainty vocabulary | extension slots only |
| D — Reach | 051, 052, 055 | Absence, engagement, distribution, resilience | none new — SPEC-042 shipped its own Delivery block; the remaining monitoring surface is 053's |
| E — Phase 8 made visible | 053 | Finish the projections; build the missing surfaces | **hard: phase 8 verified** |
| F — Close | 056 | Verification | all |


## Audit against the discussion (2026-08-05)

After the first ten sheets were written they were checked back against everything raised in the
review and the discussion that followed. Four items had been discussed and were in no sheet, and
reliability had been specified only as SSE reconnect. Both are now closed.

**Coverage gaps found and closed**

| Missing | Where it went |
|---|---|
| The calibration language — one uncertainty vocabulary at every altitude, the review's single "spend the design budget here" recommendation | **SPEC-054** (new) |
| Expand-in-place "why" on any claim | **SPEC-054** |
| The output-shape question at commissioning (one-page answer vs full advisory brief) | SPEC-050 |
| A settings surface — SPEC-052 referenced one that no sheet owned | SPEC-052 |

**Reliability gaps found and closed** — all in **SPEC-055** (new), and all grounded in the current code:

- The frontend has **zero `localStorage` usage today**, and phase 9 introduced four separate
  dependencies on it (cursor, altitude, draft, reactions) with no sheet handling it being
  unavailable, disabled or full.
- `useCaseView` accumulates events in an **unbounded array copied on every append**
  (`setEvents(prev => [...prev, event])`), and SPEC-046's progress heartbeats add thousands more to
  a 191-minute case.
- The only live-region markup in the entire frontend is **one `role="status"`** on the scope sheet.
  A narrator that rewrites in place would be either silent to a screen reader or would announce its
  elapsed timer every second.
- No sheet said what the user sees when the stream dies, when reconnect exhausts, or when the
  service is down — and a frozen brief is indistinguishable from a finished one.
- Non-blocking creation (SPEC-046) opens a new gap: a case that exists but whose worker never
  started.
- The theme × viewport matrix multiplies e2e run time against SPEC-037's 10-minute budget, and
  flaky screenshot tests would make SPEC-045's harness worse than useless.

## Traceability

| Review row | Recommendation | Spec |
|---|---|---|
| 1 | Honest effort estimates | 050 |
| 2 | Refetch the projection on events | 047 |
| 3 | SSE reconnect with the existing cursor | 047 |
| 4 | `role_invocation_started` + progress heartbeat | 046 |
| 5 | Narrator line — who is speaking and what they attack | 047, 049 |
| 6 | Non-blocking case creation; draft-persist the prompt | 046, 050 |
| 7 | Objections as margin notes | 049 |
| 8 | Dissent banner | 049 |
| 9 | Case map with loops and counters | 047 |
| 10 | Tab title, notifications, away digest | 051 |
| 11 | Reactions; watch-or-notify | 050, 051 |
| 12 | Token layer, type scale, border discipline | 045, 048 |
| 13 | Persistent chrome; decision question as title | 048 |
| 14 | Three altitudes on one surface | 048 |
| 15 | Checkpoint disclosure; answer-first delivery | 050 |
| 16 | Calibration screen + outcome prompt | 046, 051 |
| 17 | Export / share; replay as onboarding | 052 |
| 18 | Standing note channel | 051 |
| 19 | Library cards, grouping, command-K, mobile | 052 |
| — | Calibration language; expand-in-place (review areas 04, 07) | 054 |
| — | Resilience, announcement policy, budgets (audit) | 055 |

Plus the work phase 8 creates and does not render, which the review could not have anticipated:

| Phase 8 output | Spec |
|---|---|
| Objective weights, computed ranking, rank-disagreement finding | 050 slot → 053 |
| Independent reviewer dissent (blocking) | 049 → 053 |
| "What could not be assessed" limitations | 053 |
| Diagnosticity matrix | 053 |
| Typed action plan | 050 slot → 053 |
| Monitoring plan, risk register, due checks | 053 (surfaces); 051 (due-check notifications) |
| Private evidence provenance | 049 → 053 |

## Findings from reviewing the existing sheets

Two discrepancies surfaced while calibrating spec size. Both are recorded here for reconciliation;
neither blocks phase 9, but both change what "new work" means.

1. **SPEC-035 is marked `verified`, but two of its scoped deliverables are absent from the
   codebase.** Its Scope section covers the Notification API ("permission prompt at first run start;
   two classes… in-app fallback banner when permission is denied") and export ("download the
   deterministic Markdown; print stylesheet for PDF"). Neither `Notification` nor any export/print
   path appears anywhere in `frontend/src/`. Phase 9 picks both up in SPEC-051 and SPEC-052 — they
   should be understood as completing SPEC-035, not as new scope. *(Reconciled 2026-08-06:
   SPEC-035's sheet now carries the two items unchecked with the deferral recorded, so the
   sheets agree.)*

2. **SPEC-037's acceptance criterion "Axe passes… on the six covered screens in both themes" is
   checked, but only one theme exists** and `frontend/e2e/` contains no `colorScheme` or theme
   handling at all. SPEC-045 introduces the second theme and the theme matrix, which is what makes
   that criterion satisfiable. *(Reconciled 2026-08-06: SPEC-037's criterion and scope now say so
   in place. The same sweep added the mobile project below, so gap 3 in the testing list is
   partially closed — a 390×844 viewport runs the library and scope-checkpoint flows.)*

## Open questions for approval

1. **Overlap with phase 8.** SPEC-038–044 are being developed in a separate worktree and are not
   visible from here. If any of it touches `frontend/src/styles.css`, `useCaseView`, `SSEClient` or
   the service endpoints, SPEC-045 and SPEC-046 need `depends_on` set against it before either is
   approved.
2. **ROADMAP registration.** `specs/ROADMAP.md` has deliberately not been edited, to avoid
   conflicting with phase 8's own roadmap updates in the other worktree. The phase 9 row should be
   added when phase 8 merges.
3. **Is SPEC-048 one session?** It is the largest sheet and carries shell, hierarchy and altitude
   together. Splitting it into shell+chrome and document+altitude is the pre-agreed fallback.
