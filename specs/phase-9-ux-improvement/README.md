# Phase 9 — UX Improvement

**Status:** planning. No spec sheets written yet — this document is the big picture they will be cut from.
**Spec range:** SPEC-045 → SPEC-054 (10 specs). SPEC-038–044 are phase 8 (pipeline improvement), `in_progress`.
**Source:** the UX review at `report-and-findings/2026-08-04-ux-review.md` (11 areas, 19 sequenced recommendations),
reconciled against phase 8 at `d179f2b`.

> ### Phase 8 is about to ship seven invisible features
>
> Reviewed against the merged phase 8 drafts: **not one of SPEC-038–044 mentions the frontend,
> `CaseView`, or the UI anywhere.** Phase 8 builds objective weights and a computed ranking, an
> independent reviewer whose dissent blocks delivery, a diagnosticity matrix, a typed action plan, a
> monitoring plan with a risk register, and a private evidence channel — and projects none of it into
> the read model or onto a screen.
>
> This is the exact failure the UX review found with `calibration.py`: fully built, fully tested, no
> endpoint, no screen, never shown to anyone. Phase 8 is set to repeat it seven times.
>
> Phase 9 therefore takes on a job it did not originally have: **SPEC-053 projects and renders phase
> 8's outputs.** Without it, phase 8's value is reachable only by reading YAML in `cases/`.

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

Every phase 8 spec produces something a user should see. None of them says who renders it.

| Phase 8 spec | Produces | Phase 9 impact |
|---|---|---|
| 038 value-model binding | Objective weights **elicited at the scope checkpoint**; deterministic ranking; a gate finding when computed and stated rank disagree | Direct collision with **050**, which redesigns that sheet. 050 builds an extension slot; **053** fills it. Rank disagreement is a new thing the UI must be able to show. |
| 039 independent review + limitations | A reviewer on a **third** model family whose dissent **blocks delivery**; an explicit "what could not be assessed" statement | **049** must treat dissent as three-voiced, not two. The limitations statement is a new delivery element (**053**). |
| 040 competing hypotheses | A diagnosticity matrix: evidence × alternatives, ranked by *disconfirming* evidence | A substantial new UI object with no home in the original plan. Goes to **053**, surfaced through **048**'s context panel. |
| 041 typed action plan | `NextAction` with owner, date, first step, cost, dependencies, urgency | Replaces the current `next_actions` string list on delivery. **050** leaves a slot; **053** fills it. |
| 042 monitoring + post-delivery | Monitoring plan, risk register, `advisor watch`, closes the loop into Brier calibration | Supersedes phase 9 *building* the outcome loop. **051** renders it. `advisor watch` is CLI-only — another surface with no screen. |
| 043 private evidence channel | User files in `cases/<id>/inputs/`; open intake questions; `source_type: user_document` | Supersedes phase 9's note channel entirely. **049** must render this provenance as its own voice — §15 requires distinguishing user-supplied information from agent interpretation. |
| 044 phase 8 re-evaluation | Measurement of phase 8 | None. |

**No file-level conflict.** Phase 8 touches none of `styles.css`, `useCaseView`, `SSEClient`, or the
service endpoints, so SPEC-045 and SPEC-046 can start immediately and in parallel with phase 8. Only
SPEC-053 hard-depends on phase 8 being verified — the dependency risk is deliberately isolated in
one spec so a phase 8 slip blocks one sheet rather than three.

## Sizing: why 10 and not 17

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
whole web product in 11 specs; phase 9 is a smaller body of work, so 9 was the proportionate number
— plus SPEC-053 for phase 8's rendering, giving 10.

Compression applied:

| Original | Now | Why |
|---|---|---|
| 047 stream + 048 narrator + 049 case map | **047** | All three are "the interface says what is actually happening" |
| 050 shell + 051 document + 052 altitudes | **048** | All three restructure the same surfaces; directly analogous to SPEC-035's breadth |
| 054 commissioning + 055 checkpoints | **050** | The three human moments: create, scope, sign |
| 056 presence + 057 engagement + 058 calibration | **051** | Everything about the user when they are not reading |
| 059 share/replay + 060 library/mobile | **052** | Reach and distribution |

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
   `Desktop Safari`). No mobile viewport is ever exercised.
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

## Sequencing

Four waves. Within a wave, specs are `parallel_with` each other; waves are sequential.

| Wave | Specs | Job | Phase 8 dependency |
|---|---|---|---|
| A — Foundation | 045, 046 | Design system + test harness; the backend additions | none — can start now |
| B — Truth and form | 047, 048 | Say what is happening; rank the information | none |
| C — Substance | 049, 050 | The deliberation; the three human moments | extension slots only |
| D — Reach | 051, 052 | Absence, engagement, distribution | 051 renders SPEC-042's outputs |
| E — Phase 8 made visible | 053 | Project and render everything phase 8 built | **hard: phase 8 verified** |
| F — Close | 054 | Verification | all |

---

### SPEC-045 — Design system: tokens, type scale, theming, and the visual-regression harness

**Includes.** The token layer, the second theme, and the test harness the rest of the phase is
verified against. Deliberately no layout or component restructuring — this is a substitution pass,
so its diff stays reviewable.

**Implements.** `frontend/src/styles/tokens.css` with color, space, type, radius, elevation and
motion primitives plus semantic aliases (`--surface-raised`, `--state-needs-you`,
`--state-uncertain`). A type scale with a real top end — display sizes for the recommendation, which
today has none. A dark theme via `prefers-color-scheme` with a `data-theme` override. Migration of
the 28 raw hex values and 9 ad-hoc font sizes now inline in `styles.css`. Playwright projects for the
theme × viewport matrix (light/dark × desktop/mobile), a reduced-motion project, and screenshot
baselines for every route.

**Tests.** A token lint that fails on any raw hex or raw `rem` font-size outside `tokens.css`,
wired into `make frontend-check` beside the existing drift check. Contrast assertions for every
semantic foreground/background pair in both themes. Baseline screenshots for all ~13 routes across
the matrix. Axe extended from 6 screens to every route, in both themes — which also makes
SPEC-037's existing "both themes" criterion true for the first time.

**Depends on.** Nothing. Parallel with 046.

---

### SPEC-046 — Service additions: progress events and projection reads

**Includes.** Every backend change phase 9 needs except the note artifact, gathered into one spec so
the backend is opened once, reviewed once, and closed.

**Implements.** `role_invocation_started` emitted before the backend call and
`role_invocation_progress` on a ~20 s timer while an invocation runs, both carrying role, task,
model and elapsed; two rows in `lexicon_data.yaml`. `new_case` returning immediately via the
`spawn_worker_background` runner that `approve_framing` already uses. `needs_you` on `CaseSummary`.
`GET /api/calibration` over `MemoryStore.calibration()`.

**Tests.** Unit: both events emitted with correct payloads on a stub backend, including on failure
and retry paths; the progress timer stops when the invocation returns and cannot outlive it.
Contract: the SSE stream carries both new types translated through the lexicon; `POST /api/cases`
returns before the worker reaches its halt; the list endpoint's `needs_you` matches the projection's
value for the same case; the calibration endpoint returns the honest small-sample copy under five
outcomes. Regression: **zero diff in `state_machine.py` transitions and handlers**, asserted as a
test — the no-flow-change guarantee.

**Depends on.** Nothing. Parallel with 045.

---

### SPEC-047 — The live case: streaming truth, the narrator, and the case map

**Includes.** Everything that makes the interface report what is actually happening. Today the
projection is fetched once per mount and never again, so the living brief is frozen at page load;
the stream carries no event during the longest wait; and the phase strip cannot express a loop.

**Implements.** Debounced `/view` refetch in `useCaseView` on non-technical events. Reconnect with
exponential backoff in `SSEClient`, resuming from `since=<cursor>`, with the last-seen cursor
persisted per case. A pure event→narration reducer and the narrator component that rewrites one
present-tense line in place, with a collapsed transcript. Plain-language loop announcements when
`stop_decision` routes to repair or `review` routes back to `synthesis`. The case map replacing
`MethodStrip`: stages grouped under their phase, return brackets for the four intra-phase cycles,
and live round counters from `repair_cycle`, `synthesis_retries`, `framing_revisions` and
`final_revisions`. Removal of the `[line_cursor]` event list.

**Tests.** Unit: the narration reducer over recorded audit fixtures; refetch debounce coalesces
bursts; reconnect resumes at the right cursor with no duplicates. Component: the map renders each of
the four cycles from fixtures, and `repair_cycle=2` reads "round 2 of 2". E2E (replay): the narrator
line changes as a recorded case advances, and a brief section appears without a page reload; the
regression the old strip had — a second challenge round rendering identically to the first — is
asserted against. Terminology guard extended so no raw `event_type` or `line_cursor` reaches the DOM.

**Depends on.** 046.

---

### SPEC-048 — The reading room: shell, chrome, hierarchy, and altitudes

**Includes.** The visual restructure. The largest spec in the phase and the natural split point if
it does not fit one session.

**Implements.** The three-region shell (rail / content / context panel). Persistent case chrome
carrying the decision question — replacing `view.case_id`, which today renders a slug like
`case-014-should-i-take-the-ser` as the page heading — plus phase and live spend. Removal of the ten
`← back` links and the second tab bar, and consolidation of the two competing case surfaces
(`CaseDetail` and `Brief`) into one. Prose treatment for brief sections with hanging labels rather
than a card per paragraph; the answer at display scale; borders reserved for two meanings only —
needs your action, or expresses uncertainty. Content-shaped skeletons replacing `<p>Loading…</p>`,
and a toast system for control actions. An Answer / Reasoning / Method altitude control persisted
per user, with rooms rendered into the context panel instead of as routes.

**Tests.** A **density guard**: bordered elements per rendered screen must not exceed a documented
budget, and the computed font-size of the recommendation must exceed every metric element on the
same screen — permanently preventing the current inversion where `.answer-recommendation` renders at
18 px and `.source-strength-grade` at 24 px in the accent color. The page heading equals the decision
question for every fixture and never matches the `case-\d+-` slug pattern; zero `.back-link`
occurrences remain. Altitude persists across cases and reloads; each altitude renders its required
elements and omits the others; opening a citation preserves scroll position; every existing room deep
link still resolves. Full visual-regression and axe passes across the matrix.

**Depends on.** 045, 047.

---

### SPEC-049 — The cast: attribution, margin objections, and dissent

**Includes.** Making the multi-agent deliberation visible. Thirteen agents work a case and two
Directors run on deliberately different model families; today an agent is named in exactly two
places in the whole UI, and the second opinion sits in a room most users never open.

**Implements.** Objections rendered against their `target_section` as margin notes carrying
resolution status — the field is already in the projection and is currently used only to print a
grey subtitle. A dissent surface above the answer, built for **three voices, not two**: the two
Directors' `track_divergence`, plus phase 8 SPEC-039's independent reviewer, whose dissent *blocks
delivery* and so must read as a harder state than disagreement. Voice attribution derived from
`BriefBlock.provenance` ("The Challenger raised this" rather than `provenance: challenge`), extended
to cover SPEC-043's `source_type: user_document` — §15 explicitly requires the interface to
distinguish user-supplied information from agent interpretation, and today it cannot. Agent-aware
narrator strings naming who is speaking and what they are contesting.

**Tests.** An objection with `target_section=X` renders adjacent to section X. `agreement=false`
renders the dissent surface; `true` does not. A blocking reviewer dissent renders distinctly from a
non-blocking Director split, and delivery cannot be signed while one is open. A **never-averaged
invariant**: the UI never displays a blended or midpoint position between tracks. Every `provenance`
value in the schema maps to a voice label, so a newly added value cannot silently render as a raw
enum — this is the test that keeps phase 8's new provenances from regressing the UI.

**Depends on.** 047, 048. Voice coverage for reviewer dissent and user documents lands here as a
slot; SPEC-053 verifies it against the real artifacts.

---

### SPEC-050 — Commissioning and checkpoints

**Includes.** The three moments a human is actually in the loop: starting a case, signing the scope,
and signing the delivery.

**Implements.** The non-blocking creation flow consuming 046's immediate response, with draft
persistence to `localStorage` and intake/framing narrated as the first demonstration of the method.
Effort estimates derived from recorded history in `memory/` — today the chips promise "roughly 10–20
minutes" while the first verified real case took 191 minutes. A scope sheet led by the restatement as
a binary question, with the other four sections collapsed under "Adjust scope" and a count of what
each contains. Delivery led by one synthesized honest sentence, with the four uncertainty encodings
moved one click down under "How sure is this?". The consequence-of-doing-nothing copy promoted into
both subheads, and a send-back confirmation naming what it spends.

**Tests.** The critical invariant: the signed `FramingApproval` / `FinalApproval` artifact is
**identical whether the user signs immediately or expands every section** — asserted in stub mode
against disk state, which the existing lifecycle test already does for gates. Reload mid-commission
preserves the prompt; the case shell renders before framing completes. A guard test that no hardcoded
minute range remains in `terms.ts`, and that an empty history yields honest fallback copy rather than
a fabricated number. Send-back requires explicit confirmation; delivery renders key reasons above the
uncertainty grid.

**Depends on.** 046, 048.

---

### SPEC-051 — Presence, engagement, and the outcome loop

**Includes.** Everything about the user when they are not reading the screen. Runs reach 191 minutes
and nothing currently tells anyone to come back. **SPEC-035 already scoped the Notification API and
it was never built** (see Findings below) — this spec completes that scope rather than opening new
ground.

**Implements.** Tab title as a progress channel; the Notification API with permission requested at
first run start, two classes (needs-you, ready) and an in-app fallback when denied — as SPEC-035
specified. A "while you were away" digest computed from the cursor persisted in 047. Live spend in
the chrome. Reactions on assumptions and objections as they appear, collected client-side to pre-fill
the delivery revision note. A calibration screen consuming 046's endpoint.

**Superseded by phase 8, deliberately not built here.** The standing note channel — SPEC-043's
private evidence channel is the better version and produces real evidence records. The outcome loop
— SPEC-042 closes it into the Brier machinery; this spec renders it and drives the prompt, and the
`advisor watch` due-checks surface moves to SPEC-053.

**Out of scope, deliberately.** Showing the issue tree *at* the scope gate. The tree is produced by
`structuring`/`planning`, which run after `awaiting_framing_approval`; moving it earlier is a stage
reordering and the phase constraint forbids it. The tree is instead surfaced with reactions when it
is produced. Flagged for a later phase.

**Tests.** The digest computed from a cursor-gap fixture matches expected counts, and is suppressed
rather than rendered empty when nothing happened. No notification without permission. Reactions
survive reload. Under five outcomes the calibration screen renders the "this is noise, not a
calibration estimate" copy verbatim, and the case view never reads calibration.

**Depends on.** 046, 047, 048.

---

### SPEC-052 — Distribution: export, share, replay onboarding, library, and mobile

**Includes.** Making the brief an object that can leave the tool, and the library a workspace.
**SPEC-035 already scoped Markdown export and a print stylesheet and neither was built** — this
completes that too.

**Implements.** Brief export (deterministic Markdown download and print stylesheet for PDF) and a
read-only share link with citations intact. Replay mode — which exists, takes a speed factor, and is
used only by tests — promoted into first-run onboarding: a recorded case at 60×, showing a full
deliberation with its loops and dissent in ninety seconds. Case cards with phase ring, elapsed
against estimate, spend against cap and the current narrator line, grouped by 046's `needs_you`
field, which deletes the duplicated client-side derivation in `CaseLibrary.tsx`. Search and
command-K. Responsive breakpoints so the two checkpoints and the answer work on a phone.

**Tests.** The exported brief contains every citation id present in the projection. The share link
renders read-only and rejects control POSTs — replay mode already enforces this, so the test extends
an existing guarantee. The tour completes over a recorded fixture. The library consumes the server's
`needs_you` and the client-side stage-string derivation is gone. Mobile-viewport e2e for both
checkpoints and the answer, with no horizontal body scroll at 360 px.

**Depends on.** 045, 048, 049.

---

### SPEC-053 — Phase 8 made visible: projection and rendering

**Includes.** The read model and the screens for everything phase 8 built and never surfaced. This
is the one spec that hard-depends on phase 8, so the dependency risk is contained here rather than
spread across three sheets.

**Implements.** `caseview.py` extended to project phase 8's artifacts into `CaseView`, with the
generated TypeScript types following automatically through the existing drift check. Then the
screens: objective weights and the deterministic ranking on the scope sheet, filling SPEC-050's
extension slot, including the gate finding when computed and stated rank disagree — a disagreement a
user must be able to see, not just an auditor. The diagnosticity matrix from SPEC-040 as an
evidence × alternatives grid in the context panel, ranked by disconfirming evidence, reachable from
any alternative. The typed `NextAction` plan on delivery — owner, date, first step, cost,
dependencies, urgency — replacing the current string list. The monitoring plan and risk register
from SPEC-042, with an `advisor watch` equivalent showing which checks are due. The
"what could not be assessed" limitations statement from SPEC-039 in the integrity slip. Private
evidence from SPEC-043 rendered with `user_document` provenance in its own voice.

**Tests.** Every phase 8 artifact type has a projection test and a rendering test — the acceptance
criterion is that **no phase 8 output is reachable only by reading YAML**, asserted by enumerating
phase 8's artifact types and failing on any that no screen consumes. Rank disagreement renders
visibly rather than silently. A blocking limitation or reviewer dissent prevents signing. Axe,
visual-regression and terminology-guard passes for every new surface, per the phase testing
contract. Fixtures extended with a phase 8 case so the suite covers the new shapes.

**Depends on.** Phase 8 verified (SPEC-044); and 048, 049, 050, 051.

---

### SPEC-054 — Phase 9 verification

**Includes.** No new functionality. Closes the phase the way phases 4, 5 and 7 were closed.

**Tests.** Full visual regression across the theme × viewport matrix against 045's baselines. The
complete e2e suite across fixture, stub and replay, matching SPEC-037's structure and runtime
budget. Axe clean on every route in both themes. One real case run end to end on the new UI —
exercising phase 8's pipeline so the run covers both phases — written up in `report-and-findings/`
as SPEC-020 and SPEC-022 did. A final audit that the backend surface matches the table at the top of
this document and nothing else changed, and that every phase 8 artifact type reaches a screen.

**Depends on.** All of 045–053.

---

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

Plus the work phase 8 creates and does not render, which the review could not have anticipated:

| Phase 8 output | Spec |
|---|---|
| Objective weights, computed ranking, rank-disagreement finding | 050 slot → 053 |
| Independent reviewer dissent (blocking) | 049 → 053 |
| "What could not be assessed" limitations | 053 |
| Diagnosticity matrix | 053 |
| Typed action plan | 050 slot → 053 |
| Monitoring plan, risk register, due checks | 051, 053 |
| Private evidence provenance | 049 → 053 |

## Findings from reviewing the existing sheets

Two discrepancies surfaced while calibrating spec size. Both are recorded here for reconciliation;
neither blocks phase 9, but both change what "new work" means.

1. **SPEC-035 is marked `verified`, but two of its scoped deliverables are absent from the
   codebase.** Its Scope section covers the Notification API ("permission prompt at first run start;
   two classes… in-app fallback banner when permission is denied") and export ("download the
   deterministic Markdown; print stylesheet for PDF"). Neither `Notification` nor any export/print
   path appears anywhere in `frontend/src/`. Phase 9 picks both up in SPEC-051 and SPEC-052 — they
   should be understood as completing SPEC-035, not as new scope.

2. **SPEC-037's acceptance criterion "Axe passes… on the six covered screens in both themes" is
   checked, but only one theme exists** and `frontend/e2e/` contains no `colorScheme` or theme
   handling at all. SPEC-045 introduces the second theme and the theme matrix, which is what makes
   that criterion satisfiable.

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
