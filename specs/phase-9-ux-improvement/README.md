# Phase 9 — UX Improvement

**Status:** planning. No spec sheets written yet — this document is the big picture they will be cut from.
**Spec range:** SPEC-045 → SPEC-061 (17 specs). SPEC-038–044 belong to phase 8, developed in a separate worktree.
**Source:** the UX review at `report-and-findings/2026-08-04-ux-review.md` (11 areas, 19 sequenced recommendations).

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
schema is modified. Across all 17 specs the backend surface is:

| Addition | Spec | Kind |
|---|---|---|
| `role_invocation_started`, `role_invocation_progress` audit events + 2 lexicon rows | 046 | additive |
| `new_case` returns before the worker halts (uses the existing `spawn_worker_background`) | 046 | control-layer |
| `needs_you` on the case-list endpoint | 046 | additive field |
| `GET /api/calibration` over the existing `MemoryStore.calibration()` | 046 | additive read |
| One user-note artifact type + its inclusion in role context | 057 | additive artifact |

Everything else — 15 of 17 specs — is frontend only. SPEC-046 carries a regression test asserting
zero diff in `state_machine.py` transitions and handlers, so "the pipeline did not change" is a
checkable claim rather than a promise.

## Why 17 specs

`specs/README.md` says: *"Keep specs small. A spec that cannot be implemented and verified in one
focused session should be split."* Nineteen recommendations across eleven problem areas do not fit
in eleven specs without violating that rule. Seventeen is the count at which each spec is one
session with one coherent job and one verifiable outcome.

If a leaner board is wanted, three merges are safe and take it to 14: **047+048** (both are "the
stream tells the truth"), **050+051** (both restructure the same screens), **059+060** (both are
reach). No other pair should be merged — the rest either cross a dependency boundary or would
produce a grab-bag spec with no single acceptance criterion.

## Sequencing

Six waves. Within a wave, specs are `parallel_with` each other unless noted; waves are sequential.

| Wave | Specs | Job |
|---|---|---|
| A — Foundation | 045, 046 | The token layer and the only backend additions. Everything else depends on these. |
| B — Truth | 047, 048, 049 | Make the interface say what is actually happening. |
| C — Form | 050, 051, 052 | Rank the information. Shell, hierarchy, altitude. |
| D — Substance | 053, 054, 055 | The deliberation, the first five minutes, the two signatures. |
| E — Reach | 056, 057, 058, 059, 060 | Absence, engagement, retention, distribution. |
| F — Close | 061 | Verify the phase the way phases 4, 5 and 7 were closed. |

---

## Wave A — Foundation

### SPEC-045 — Design tokens, type scale, and theming

**Includes.** The token layer and its enforcement. Deliberately no layout or component
restructuring — this spec is a substitution pass, so its diff is reviewable and its risk is near
zero.

**Implements.** `frontend/src/styles/tokens.css`: color, space, type, radius, elevation and motion
primitives, plus semantic aliases (`--surface-raised`, `--state-needs-you`, `--state-uncertain`). A
type scale with a real top end — display sizes for the recommendation, which today has none. Dark
theme via `prefers-color-scheme` with a `data-theme` override. Migration of the 28 raw hex values
and 9 ad-hoc font sizes currently inline in `styles.css`.

**Tests.** A CI guard script — mirroring the existing type-generation drift check — that fails if
any raw hex or raw `rem` font-size appears outside `tokens.css`. Contrast assertions for every
semantic foreground/background pair in both themes. Playwright screenshot baselines for every route
in both themes; this spec is where the visual-regression harness lands, because every later spec
needs it.

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

**Tests.** Unit: both events emitted with correct payloads on a stub backend, including on the
failure and retry paths; the progress timer stops when the invocation returns and cannot outlive it.
Contract: the SSE stream carries both new types translated through the lexicon; `POST /api/cases`
returns before the worker reaches its halt; the list endpoint's `needs_you` matches the projection's
value for the same case; the calibration endpoint returns the honest small-sample copy under five
outcomes. Regression: **assert zero diff in `state_machine.py` transitions and handlers** — the
no-flow-change guarantee, as a test.

**Depends on.** Nothing. Parallel with 045.

---

## Wave B — Truth about what is happening

### SPEC-047 — Live projection and resilient stream

**Includes.** Making already-streamed data reach the rendered content. The single highest-value
repair in the phase and one of the smallest.

**Implements.** Debounced `/view` refetch in `useCaseView` whenever a non-technical event lands —
today the projection is fetched once per mount and never again, so the living brief is frozen at
page load. Reconnect with exponential backoff in `SSEClient`, resuming from `since=<cursor>`.
Last-seen cursor persisted per case (which SPEC-056 then reuses).

**Tests.** Unit: the refetch debounce coalesces event bursts into one request; reconnect resumes at
the correct cursor and delivers no duplicates. E2E: a brief section appears without a page reload;
killing and restoring the stream mid-run loses no events.

**Depends on.** 046.

---

### SPEC-048 — The narrator

**Includes.** Replacing the raw event log with one present-tense line that rewrites in place, and
announcing loops in plain language.

**Implements.** A pure event→narration reducer (unit-testable in isolation). The narrator component:
current role, what it is working on, elapsed, task counter. A collapsed transcript behind it.
Plain-language loop announcements when `stop_decision` routes to repair or `review` routes back to
`synthesis`. Deletion of the `[line_cursor]` event list from the case page.

**Tests.** Reducer unit tests over recorded audit fixtures — the repo already has fixtures and
replay mode, so this is cheap. Assert no raw `event_type` or `line_cursor` reaches the DOM
(extending the existing no-raw-enum discipline). E2E over replay mode asserting the line changes as
a recorded case advances.

**Depends on.** 046, 047.

---

### SPEC-049 — The case map: cycles and round counters

**Includes.** Replacing `MethodStrip`, which cannot express a loop, with a map that can.

**Implements.** The case-map component: stages grouped under their phase, return brackets for the
four intra-phase cycles, current-stage marker. Live round counters from `repair_cycle`,
`synthesis_retries`, `framing_revisions` and `final_revisions` — all already in `CaseState` and
today visible only as raw meters in the Method room. Loop budgets shown as the promise they are
("argues with itself at most twice, then commits").

**Tests.** Fixture-driven render for each of the four cycles. Given `repair_cycle=2`, the map reads
"round 2 of 2". A regression test for the defect the old strip had: a case in its second challenge
round must not render identically to a case in its first.

**Depends on.** 045.

---

## Wave C — Form

### SPEC-050 — App shell and persistent case chrome

**Includes.** Navigation and case identity only — no content restructuring, which is 051's job.

**Implements.** The three-region shell (rail / content / context panel). Persistent case chrome
carrying the decision question — replacing `view.case_id`, which today renders a slug like
`case-014-should-i-take-the-ser` as the page heading — plus phase and live spend. Removal of the ten
`← back` links and the second tab bar. Consolidation of the two competing case surfaces
(`CaseDetail` and `Brief`) into one.

**Tests.** The page heading equals the decision question for every case fixture and never matches
the `case-\d+-` slug pattern. Assert zero `.back-link` occurrences remain. Keyboard navigation and
focus order through the three regions. Axe pass on the shell.

**Depends on.** 045.

---

### SPEC-051 — The brief as a document

**Includes.** Hierarchy and border discipline applied to brief and delivery content.

**Implements.** Prose treatment for brief sections — hanging labels, no card per paragraph. The
answer at display scale. Borders reserved for exactly two meanings: needs your action, or expresses
uncertainty. Content-shaped skeletons replacing `<p>Loading…</p>`. A toast system for control
actions, which today either silently swap the screen or render a red paragraph.

**Tests.** A **density guard**: bordered elements per rendered screen must not exceed a documented
budget, and the computed font-size of the recommendation must exceed every metric element on the
same screen. That second assertion permanently prevents the current inversion, where
`.answer-recommendation` renders at 18 px and `.source-strength-grade` at 24 px in the accent color.
Visual regression against 045's baselines.

**Depends on.** 045, 050.

---

### SPEC-052 — Altitudes and the context panel

**Includes.** The answer-first / detail-on-demand split that serves both audiences from one surface.

**Implements.** An Answer / Reasoning / Method control, persisted per user rather than per case.
Rooms rendered into the context panel instead of as routes, with existing deep links still
resolving. An expand-in-place "why" affordance on claims, so following evidence does not cost you
your place in the argument.

**Tests.** Altitude persists across cases and reloads. Each altitude renders its required elements
and omits the others. Opening a citation preserves scroll position in the argument. Every existing
room deep link still resolves.

**Depends on.** 050, 051.

---

## Wave D — Substance

### SPEC-053 — The cast: attribution, margin objections, dissent

**Includes.** Making the multi-agent deliberation visible. Thirteen agents work a case and two
Directors run on deliberately different model families; today an agent is named in exactly two
places in the whole UI.

**Implements.** Objections rendered against their `target_section` as margin notes carrying
resolution status — the field is already in the projection and is currently used to print a grey
subtitle. A dissent banner above the answer when `track_divergence.agreement` is false. Voice
attribution derived from `BriefBlock.provenance` ("The Challenger raised this" rather than
`provenance: challenge`). Agent-aware narrator strings.

**Tests.** An objection with `target_section=X` renders adjacent to section X. `agreement=false`
renders the banner; `true` does not. A **never-averaged invariant**: assert the UI never displays a
blended or midpoint position between the two tracks. Every `provenance` value in the schema maps to
a voice label, so a new value cannot silently render as an enum.

**Depends on.** 048, 051.

---

### SPEC-054 — Commissioning and honest effort

**Includes.** The first five minutes, which are currently a disabled button and a blank screen.

**Implements.** The non-blocking creation flow consuming 046's immediate response. Draft persistence
to `localStorage` on every keystroke. Intake and framing narrated as the first demonstration of the
method. Effort estimates derived from recorded history in `memory/` — today the chips promise
"roughly 10–20 minutes" while the first verified real case took 191 minutes. The watch-or-notify
question that routes the rest of the experience.

**Tests.** Reload mid-commission preserves the prompt. The case shell renders before framing
completes. A guard test that no hardcoded minute range remains in `terms.ts`. With empty history,
the estimate falls back to honest copy rather than a fabricated number.

**Depends on.** 046, 048, 050.

---

### SPEC-055 — Checkpoints: scope disclosure and answer-first delivery

**Includes.** The two moments the product asks a human to take responsibility.

**Implements.** A scope sheet led by the restatement as a binary question, with the other four
sections collapsed under "Adjust scope" and a count of what each contains. Delivery led by one
synthesized honest sentence, with the four uncertainty encodings moved one click down under "How
sure is this?" — unchanged, just no longer standing between the answer and its reasons. The
consequence-of-doing-nothing copy promoted into both subheads. A send-back confirmation that names
what it spends, since `MAX_FINAL_REVISIONS = 1`.

**Tests.** The critical invariant: the signed `FramingApproval` / `FinalApproval` artifact is
**identical whether the user signs immediately or expands every section**. Send-back requires
explicit confirmation. Delivery renders key reasons above the uncertainty grid.

**Depends on.** 051, 052.

---

## Wave E — Reach

### SPEC-056 — Presence: title, notifications, away digest, live spend

**Includes.** The story for the three hours the user is not looking. Runs reach 191 minutes and
nothing currently tells anyone to come back.

**Implements.** Tab title as a progress channel. Notification API on the two gates plus failure,
with permission requested when the first case starts running and the reason is self-evident. A
"while you were away" digest computed from the cursor persisted in 047. Live spend in the chrome
from `EffortView`.

**Tests.** The digest computed from a cursor-gap fixture matches expected counts. Title updates on
phase change and on gate arrival. No notification is issued without permission. The digest is
suppressed rather than rendered empty when nothing happened.

**Depends on.** 047, 050.

---

### SPEC-057 — Engagement: reactions and the standing note channel

**Includes.** Giving the user something to do between the two signatures — currently the complete
mid-run input surface is empty.

**Implements.** Reactions on assumptions and objections as they appear ("this is wrong", "this one
matters"), collected client-side and used to pre-fill the delivery revision note. A standing note
channel: one always-available box landing as an additive artifact the next role reads from the
blackboard. The issue tree surfaced with reactions **when it is produced**, so branches can be
deprioritised during investigation.

**Out of scope, deliberately.** Showing the issue tree *at* the scope gate. The tree is produced by
`structuring`/`planning`, which run after `awaiting_framing_approval`; moving it earlier is a stage
reordering and the phase constraint forbids it. Flagged here for a later phase.

**Tests.** Reactions survive reload. The note artifact validates against its schema and appears in
the next role's context. A note added mid-run changes no stage or transition — asserted, not
assumed. The issue tree renders with materiality per node.

**Depends on.** 047, 052.

---

### SPEC-058 — Calibration and the outcome loop

**Includes.** The most SaaS-shaped thing in the codebase, already written and never shown:
`calibration.py` computes a Brier score of forecasts against realized outcomes, and no endpoint
served it and no screen read it.

**Implements.** A calibration screen consuming 046's endpoint. An outcome prompt scheduled after a
decision, reusing 056's notification path. Honest small-sample presentation.

**Tests.** Under five outcomes, the "this is noise, not a calibration estimate" copy renders
verbatim. Brier score, mean forecast and mean realized rate all render. The invariant that
calibration never influences a live case: assert the case view never reads it.

**Depends on.** 046, 056.

---

### SPEC-059 — Share, export, and replay onboarding

**Includes.** Making the brief an object that can leave the tool, and using an existing capability
as the product tour.

**Implements.** Brief export (print stylesheet and PDF) and a read-only share link with citations
intact. Replay mode — which exists, takes a speed factor, and is currently used only by tests —
promoted into first-run onboarding: a recorded case at 60×, showing a full deliberation with its
loops and dissent in ninety seconds.

**Tests.** The exported brief contains every citation id present in the projection. The share link
renders read-only and rejects control POSTs (replay mode already enforces this). The tour completes
over a recorded fixture case.

**Depends on.** 051, 053.

---

### SPEC-060 — Library workspace and mobile

**Includes.** The list is the dashboard for a multi-hour engagement and currently shows less than
`advisor status` does in a terminal.

**Implements.** Case cards with phase ring, elapsed against estimate, spend against cap, and the
current narrator line. Grouping by waiting-on-you / running / done using 046's `needs_you` field,
which deletes the duplicated client-side derivation in `CaseLibrary.tsx`. Search and command-K.
Responsive breakpoints so the two checkpoints and the answer are usable on a phone.

**Tests.** The library consumes the server's `needs_you` — assert the client-side stage-string
derivation is gone. Mobile-viewport e2e for both checkpoints and the answer. No horizontal body
scroll at 360 px.

**Depends on.** 046, 050, 048.

---

## Wave F — Close

### SPEC-061 — Phase 9 verification

**Includes.** No new functionality. This spec closes the phase the way phases 4, 5 and 7 were
closed.

**Implements.** Nothing shippable — it runs the phase.

**Tests.** Full visual regression in both themes against 045's baselines. The complete phase-9 e2e
suite across the fixture, stub and replay modes, matching SPEC-037's structure. One real case run
end to end on the new UI, with the result written up in `report-and-findings/` as SPEC-020 and
SPEC-022 did. A final audit that the backend surface matches the table at the top of this document
and nothing else changed.

**Depends on.** All of 045–060.

---

## Traceability

Every spec traces to the sequenced recommendations in
`report-and-findings/2026-08-04-ux-review.md`:

| Review row | Recommendation | Spec |
|---|---|---|
| 1 | Honest effort estimates | 054 |
| 2 | Refetch the projection on events | 047 |
| 3 | SSE reconnect with the existing cursor | 047 |
| 4 | `role_invocation_started` + progress heartbeat | 046 |
| 5 | Narrator line — who is speaking and what they attack | 048, 053 |
| 6 | Non-blocking case creation; draft-persist the prompt | 046, 054 |
| 7 | Objections as margin notes | 053 |
| 8 | Dissent banner | 053 |
| 9 | Case map with loops and counters | 049 |
| 10 | Tab title, notifications, away digest | 056 |
| 11 | Reactions; watch-or-notify | 054, 057 |
| 12 | Token layer, type scale, border discipline | 045, 051 |
| 13 | Persistent chrome; decision question as title | 050 |
| 14 | Three altitudes on one surface | 052 |
| 15 | Checkpoint disclosure; answer-first delivery | 055 |
| 16 | Calibration screen + outcome prompt | 046, 058 |
| 17 | Export / share; replay as onboarding | 059 |
| 18 | Standing note channel | 057 |
| 19 | Library cards, grouping, command-K, mobile | 060 |

## Open questions for approval

1. **Overlap with phase 8.** Phase 8 (SPEC-038–044) is being developed in a separate worktree and
   is not visible from here. If any of it touches `frontend/src/styles.css`, `useCaseView`,
   `SSEClient` or the service endpoints, SPEC-045 and SPEC-046 need their `depends_on` set against
   it before either is approved.
2. **ROADMAP registration.** `specs/ROADMAP.md` has deliberately not been edited, to avoid a
   conflict with phase 8's own roadmap updates in the other worktree. The phase 9 row should be
   added when phase 8 merges.
3. **Merge to 14?** The three safe merges are noted above. Worth deciding before sheets are written,
   since it changes the numbering.
