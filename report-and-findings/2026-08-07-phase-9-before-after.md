# SPEC-056 — Phase 9 re-evaluation: before/after on the new surface (findings)

**Date:** 2026-08-07
**Phase:** 9 (UX improvement), SPEC-045 → SPEC-056
**Branch:** `claude/ux-saas-experience-i8hs0d`
**Sheets covered:** SPEC-045 … SPEC-055 (eleven), closed by this one — all `implemented`; none is
marked `verified`, and this sheet does not promote them

Phase 9's claim is that the product now communicates what it does, and it rests on a structural
promise: that a UX phase changed no pipeline behaviour. This report is the evidence for both, plus
the measurements the phase's UX claims stand or fall on. It records what did not improve and what
could not be run as plainly as what did.

## Summary

The structural promise holds, and holds tightly: across phase 9's fourteen commits, `orchestrator/`
moved by **+393 / −24 lines across six files**, every line of which is a new audit emit, a new read
route, a projection addition, a presentation string, or one parameter. `tests/test_pipeline_invariants.py`
passes.

The headline UX claim is measured rather than asserted. On the profile of the repo's one real
case — 45 invocations, 178.4 min in flight, 191 min wall clock — the interface could name the
running role for **at most 6.6%** of the run before the phase and **at least 93.4%** after it.

Five defects were found. Two are product defects, filed and not fixed, per this sheet's rule that
defects return to the spec that owns them; one of them — a whole class of prompts that cannot start
a case at all — is the most serious finding in this report. The other three are defects *in the
verification harness itself*, which the sweep could not run without: one was fixed here, one turned
out to have been fixed on `main` a day earlier by an independent sweep that tripped over exactly the
same thing, and one — a coverage guard resting on a gitignored fixture, green only on machines where
an untracked file happened to exist — was found by accident and fixed.

Of the sheet's eight acceptance criteria, **four are met, two are partial and two are not met**. The
two outright failures are the visual suite, which does not pass twice consecutively, and the one real
live-model case, which was not run. The two partials are `make e2e-frontend`, which cannot complete
in a container without webkit, and the visual half of the visual/axe criterion. SPEC-056 is therefore
`implemented`, not `verified`, and phase 9 is recorded that way.

> **Read this alongside the follow-up below.** Everything above is the sweep as it stood on the day.
> All five defects have since been fixed, two of them turned out to be larger than recorded here, one
> stated cause was wrong, and the visual suite now passes twice consecutively — so that criterion is
> met and the count above is out of date. The corrections are kept beside the original findings
> rather than folded into them, because what a sweep got wrong is part of what it found.

## Verification sweep

| Gate | Command | Outcome |
|---|---|---|
| Python lint, types, units | `make check` | **green** — ruff + mypy clean, **968 passed**, 105s |
| Frontend types, tokens, units | `make frontend-check` | **green** — tsc clean, 64 schemas (0 drift), token guard clean, **414 passed** in 33 files |
| Production build | `make frontend-build` | **green** — 393.63 kB JS / 78.17 kB CSS |
| e2e, all three modes | see note below | **green on 5 of 6 projects** — fixture 189, stub 6, replay 12 |
| Pipeline invariants | `uv run pytest tests/test_pipeline_invariants.py` | **green** — 7 passed |
| Phase 8 coverage guard | `coverage.spec.ts` | **green** — 7 engine outputs, plus its self-guard |
| Measurement instrument | `tests/test_phase9_measure.py` | **green** — 16 passed |

**These figures are the sweep as executed, on the branch before `main` was merged in.** `main` had
moved on by six commits, and merging it brought its tests with it: on the merged tree the same two
gates read **1002 passed** and **418 passed**. Both sets are green; the counts differ only because
the tree does. Anyone running these commands against this PR will see the larger numbers.

**`make e2e-frontend` itself did not run to completion here, and cannot.** The target runs every
project, including `webkit`, and that browser is absent from this container: it is not installed and
`npx playwright install webkit` fails with `Download failure` behind the environment's proxy. What
was actually executed is the three modes in one sequential pass, scoped to the five chromium-based
projects, with `PW_CHROME` pointed at the headless shell:

```
PW_CHROME=<...>/chromium_headless_shell-1194/chrome-linux/headless_shell \
E2E_MODE={fixture,stub,replay} npx playwright test --config=e2e/playwright.config.ts \
  --project=chromium --project=chromium-dark --project=mobile --project=mobile-dark \
  --project=reduced-motion
```

So the `make check` / `make frontend-check` rows above are literally the documented commands; this
row is not. The webkit gap is an environment limitation rather than a code result — the functional
journeys webkit covers were exercised on chromium — but "the full matrix is green" is a claim this
sweep cannot make, and the criterion is met only for five of the six projects.

**e2e budget.** Three modes, five projects: **589s (9m49s)** in the sequential pass — inside
SPEC-037's ten-minute budget, but only just, and without webkit's share. Fixture mode is ~550s of
that; stub (22s) and replay (18s) are nearly free. The budget is effectively spent on the fixture
matrix, and the next sheet that adds a route to the axe or visual sweeps will breach it. (That
sequential pass is also the one whose fixture leg hit the `room-method` flake below: 188 passed + 1
failed. The clean fixture run, timed separately, was 550s for 189 passed.)

**axe.** 15 routes × both themes (`chromium`, `chromium-dark`, `mobile-dark`), **zero serious or
critical violations**.

## The measured claims

SPEC-056 names five before/after comparisons. All five are recorded below with their method,
including the one whose honest answer is weaker than the sheet implies.

### 1. Proportion of wall clock with an accurate current activity

**Before: at most 6.6%. After: at least 93.4%.**

The method is implemented in `scripts/phase9_measure.py` and tested against hand-computable
timelines in `tests/test_phase9_measure.py`. Walk the run second by second and ask whether the
interface could name the role running *at that second*. It could if a role-naming event landed
within SPEC-046's 20s cadence **and** no newer invocation has since started — an event describing a
call that has already been superseded names the wrong role, so it does not count.

The two timelines are computed from the same log, because every audit log ever written carries
`role_invocation_attempt` with a `duration_ms`, and that is enough to place both:

- *before* — one mark per invocation, at the instant it **returned**;
- *after* — a mark when it **started**, one every 20s while it ran, one when it returned.

This matters more than it looks. Measuring "before" by filtering SPEC-046's events out of a
post-SPEC-046 log would answer a much easier question, since such logs only exist for runs that
already had the fix.

**Source data and its limits.** The figures come from the recorded profile of `case-014-career-startup-pivot`,
the real case of SPEC-020: 45 invocations, 178.4 min summed in flight, 191 min wall clock. That
case's `audit.jsonl` is gitignored and no longer on disk, so its per-invocation gaps are
unrecoverable and the result is stated as the bounds those totals support — hence "at most" and "at
least" rather than point values. Idle time is 12.6 min, which is less than 45 × 20s, so the old
interface's ceiling is the idle time itself.

Both bounds flatter the old interface. `role_invocation_attempt` fires when a call *returns*, so
even within its 20s window it names what just finished rather than what is running.

**The stub cannot substitute.** Running the measurement against a stub-mode log gives 79.5% before
and 85.9% after — not because the phase achieved little, but because the stub returns in 10 ms, so
only 6.4% of that run is spent inside a call and there is almost no darkness to remove. The measure
is dominated by how long invocations actually take, which is exactly why a fast fixture cannot
demonstrate the claim and why the real case's profile is the right input.

### 2. Time from submitting a prompt to a rendered case surface

**Measured in stub mode over three runs: surface at 193 / 229 / 298 ms; framing checkpoint reached
at 674 / 707 / 781 ms.**

The old surface rendered nothing until the case reached its framing checkpoint, so that instant is
the comparable "before". The surface now renders at roughly a third of the time-to-framing.

The stub understates this by construction. Time-to-surface depends only on the `202` from
`POST /api/cases` and is therefore ~200 ms on any backend; time-to-framing is dominated by model
latency. On the real case, the intake invocation alone took 0.7 min, so on a live backend the same
comparison is ~200 ms against tens of seconds at minimum. The stub figure is a lower bound on the
improvement, not an estimate of it.

### 3. Is a second challenge round distinguishable from a stall?

**Before: no. After: yes — counted and named.**

`narration/reducer.ts` folds the stream into per-loop counters and emits an announcement naming the
round: "repair round 1", then "repair round 2", asserted at `reducer.test.ts:117-133`. The case map
draws all three cycles — `cycle-rescope`, `cycle-repair`, `cycle-re-review` — *before* any of them
runs, so a loop the user has already been shown reads as a plan rather than a malfunction, with
exactly one phase marked current (`replay.spec.ts:162-176`).

### 4. Count of phase 8 artifact types reachable from a screen

**Before: 0. After: 7.**

`coverage.spec.ts` names each engine output, locates it in the DOM, and guards itself: a separate
test asserts the coverage list mentions every phase 8 sheet, so deleting an entry to make the suite
pass fails a different test. Covered: objective weights (SPEC-038), independent review verdict
(SPEC-039), diagnosticity matrix (SPEC-040), typed action plan (SPEC-041), monitoring plan and risk
register (SPEC-042), source-type voices including `user_document` (SPEC-043), calibration record
(SPEC-025).

### 5. Behaviour when the service dies mid-run

**Before: a frozen brief presented as current. After: marked stale.**

The dangerous shape is a plausible recommendation on screen with nothing keeping it current — a
frozen brief and a finished brief look identical. `resilience.spec.ts` loads the projection with the
event stream refused from the first attempt and asserts the chrome stops claiming the brief is live
(`Reconnecting` / `out of date`), that an unreachable service renders as its own state rather than a
red paragraph, and that the reassurance "nothing was lost" is present — a user seeing a blank app
assumes their three-hour case is gone.

## Backend-surface audit

Phase 9's commits straddle phase 8's merge (`726baf8`), so a two-dot diff from the branch point
pulls in all of phase 8 — the risk SPEC-056's own open question flagged. The audit therefore
aggregates only phase 9's fourteen commits:

`1e320de 241040c 272e56d 074d08b 69d7eea fbe09f4 e44faf3 c67bec8 b55d672 5d96fce 9aa4a99 690bd8f 7e249ca 5997384`

| File | Δ | What changed |
|---|---|---|
| `orchestrator/invoke_role.py` | +134 / −10 | `role_invocation_started` and the `role_invocation_progress` heartbeat |
| `orchestrator/service/app.py` | +125 / −6 | non-blocking creation, `GET /api/calibration`, `GET /api/effort-history` |
| `orchestrator/service/caseview.py` | +111 / −3 | projection additions (independent review, next actions) |
| `orchestrator/control.py` | +9 / −4 | one `worker_runner` parameter on `new_case` |
| `orchestrator/service/lexicon_data.yaml` | +8 / −0 | presentation strings |
| `orchestrator/artifacts/schema_export.py` | +6 / −1 | one schema registration |
| **Total** | **+393 / −24** | **six files** |

Every addition is a read, an emit, a presentation string, or a projection field. No stage, gate,
transition, prompt, or artifact schema changed shape. The `worker_runner` parameter mirrors what
`approve_framing` and `resume` already accepted. `tests/test_pipeline_invariants.py` passes.

## Defects found

### 1. A class of prompts cannot start a case at all (product — **not fixed**)

`orchestrator/service/app.py:905` derives a slug by stripping punctuation, stripping leading and
trailing hyphens, and *then* truncating to 40 characters. When the 40-character cut lands on a word
boundary the slug ends in a hyphen, and `create_case` rejects it (`case_store.py:484`).

Found by accident: the prompt "Should I migrate the billing service to a new provider?" produces
`should-i-migrate-the-billing-service-to-` and the case cannot be created. Any prompt whose
truncation boundary falls on a space hits this. The fix is to strip after truncating rather than
before; it is one line, but this sheet does not absorb defects, so it is filed rather than applied.

### 2. Commissioning errors bypass the failure taxonomy (product — **not fixed**)

The same failure renders as a raw serialized response body in a red paragraph at the foot of
`/new` — `{"error":"validation_error","detail":"...","case_stage":null}` — rather than through
SPEC-055's `Failure` component. `NewDecision.tsx:173` still uses `<p className="error">`, which is
precisely the "red paragraph" that `resilience.spec.ts` forbids elsewhere. Related: raw enum values
leak to users as stop reasons on two surfaces (`FailurePath.tsx:73`, `Delivery.tsx:423`), e.g.
`no_critical_evidence_gaps_remain`; the terminology guard's forbidden list does not include these
values and the lexicon has no entry for them.

### 3. `make e2e-frontend` never worked from the repo root (harness — **already fixed on main**)

Each `make` recipe line runs in its own shell, so the target's `cd frontend` applied only to the
`npm install` line; the three test lines ran from the repo root and could not find the config. The
sheet's own verification plan runs through this target, so the sweep hit it immediately and fixed it
by giving each line its own `cd`.

**It was not a new finding.** Main's 2026-08-06 spec sweep had already found and fixed it, byte for
byte — which is why the two changes merged without conflicting. Recorded here as a duplicate
discovery rather than a phase 9 contribution. That two independent sweeps tripped over the same
recipe within a day is itself the useful signal: the target is on no CI path, so nothing but a human
running it end to end ever exercises it.

### 4. SPEC-053's coverage guard depended on an untracked fixture (harness — **fixed**)

The phase 8 coverage guard asserts the monitoring plan (SPEC-042) is on a screen. That plan lives
under a *memory root* rather than in the case tree, and `.gitignore` carried a bare `memory/` rule —
so the e2e fixture it reads was silently never committed. The guard passed only on a machine where
that untracked file happened to exist locally, and failed outright on a clean checkout.

This surfaced by accident: the verification container reset mid-session and took the untracked file
with it, turning a green test red with no code change. Without that, the sweep would have reported
the guard green on the strength of a file no reviewer, CI run, or fresh clone would ever have.

Fixed by narrowing the ignore rule to exempt `tests/fixtures/memory/` and committing a regenerated
plan — built through `MonitoringPlan` and written by `MonitoringStore`, so it is a schema-valid
artifact produced by the same writer the service reads with, not hand-rolled YAML. All eight
coverage tests pass, and now they pass from a clean checkout.

It is worth stating what this means for the rest of the sweep: a guard is only as good as its
reproducibility, and this one had been asserting something no one else could verify.

**And the fixture had to be reconstructed from the baseline, which exposed a second problem.** A
first regenerated plan was schema-valid but generic, and the delivery visual baseline caught it
immediately — 209,103 pixels different, confined to the monitoring block. Reading the baseline image
recovered what the original actually contained: NVDA-specific indicators consistent with the fixture
case, and one indicator rendering as `DUE NOW` against another that was not. Rebuilt to match, all
13 visual baselines and all 8 coverage tests pass **with no baseline changes at all**.

That reconstruction is what surfaced the second problem: **the fixture's rendering drifts with the
calendar.** Whether an indicator reads `DUE NOW` is computed as `(today − delivered_at).days >=
cadence` against the real clock, so the fixture's stored date decides what the Delivery screen says.
The plan is delivered `2026-07-24` with cadences of 14 and 30 days, which is the only shape yielding
the baseline's "1 check is due now." From **2026-08-23** the 30-day indicator also comes due, the
line becomes "2 checks are due now" and a second `DUE NOW` badge appears — for a fixture whose data
never changed.

> **Correction (2026-08-07, after the fix).** This section originally claimed the delivery *visual
> baseline* would fail on that date. It would not, and the claim was not checked before it was
> written. Driving the pinned date to `2026-09-01` renders the two-due state and the baseline still
> **passes**: Playwright counts **8,687 differing pixels**, about **0.12%** of the image, against a
> `maxDiffPixelRatio` of 1%. The drift is real and the fix is still right — a fixture whose output
> depends on the day it runs is not a fixture — but the consequence stated here was wrong.
>
> It also exposes something about the gate itself, which is the more useful finding: an added badge
> and a changed sentence are **invisible** to the visual suite at its current tolerance. The suite
> catches layout shifts and reflows; it does not catch modest content changes. Nothing else in the
> harness asserts that sentence, so today the drift would simply have gone unnoticed.

The fix, applied after this report was first written: `due_checks` already accepted an `as_of`, and
only the service's caller passed the real clock. `ServiceConfig` now carries `monitoring_as_of`,
read from `AGENTADVISOR_MONITORING_AS_OF` and defaulting to the real clock, and the e2e fixture
backend pins the date its baseline was captured against. Belongs to SPEC-042/SPEC-053.

### 5. The visual baselines are browser-*binary*-specific (harness — **documented**)

Pointing `PW_CHROME` at the full `chrome` binary rather than the headless shell fails 27 baselines
at once. The cause is font synthesis: bold headings render fractionally differently and the page
ends up ~5px taller, while body text is pixel-identical. Content is otherwise unchanged, so the
obvious response is to re-baseline — which would silently discard the visual gate. Recorded in
`playwright.config.ts` next to the `PW_CHROME` escape hatch that invites the mistake.

## The one reviewed baseline change

`room-options-mobile-linux.png` is updated, and it is the only baseline this work touches. The cause
is not phase 9's: merging `main` brought its SPEC-040 row badge ("least disconfirmed", on the
rank-1 option), which the phase-9 mobile baseline was captured before. At 412px the badge wraps to
two lines and the page grows 38px; at 1280px it fits, which is why the desktop and dark baselines
pass untouched and only mobile caught it.

Two things are worth stating, because a baseline update is exactly where a visual gate gets thrown
away by accident. First, the diff was read before it was accepted: identical for the first 6,698
rows, with the change confined to the badge and the reflow below it. Second, the sweep's own
tokenisation of that badge was corrected in the process — `main` set it at `0.6875rem`, below the
type scale entirely, which is what the token guard rejected; the first fix reached for `--text-sm`
(13px) and made the badge *larger* than main intended, so it now uses `--text-xs` (12px), the
nearest step on the scale.

> **Follow-up (2026-08-07): all five defects above are now fixed**, and two of them turned out to be
> larger than this report recorded.
>
> The raw enum leak was **four sites, not two**: behind `FailurePath` and `Delivery`, the projection
> composed the sentence server-side and the renderer wrote it into the exported
> `final_recommendation.md`. A fifth fell out of the fix — the lexicon substituted raw payload values
> into audit narration.
>
> The terminology guard that should have caught all of it had **two** defects, either sufficient on
> its own: it ran on two routes when the leak was on a third, and it read the DOM before the
> projection refetch had rendered the block, so it sampled the page before the offending text existed.
>
> And the visual flake's stated cause here — "the `fullPage` capture path" — was wrong. The first
> capture *paints below-fold content for the first time*, and text line boxes settle by a pixel or
> two as it does, accumulating to five. One discarded capture before the one that counts fixes it;
> the fixture matrix now passes **201/201 twice consecutively**, meeting SPEC-055's budget for the
> first time.
>
> The one finding that could not be acted on as written is the visual gate's content-blindness.
> Tightening the tolerance is impossible, not merely unattractive: at zero tolerance nine of thirteen
> routes fail on antialiasing alone, the worst at 20,616px (~0.29%), against the 8,687px (~0.12%)
> change that slipped through. The signal is below the noise. It is a layout gate, and the config now
> says so.

## Acceptance criteria not met

**The visual suite does not pass twice consecutively (SPEC-055's budget).** Across three full
fixture-matrix runs on the correct binary: one clean (189 passed), one failing `room-method`, one
failing `room-options`. Roughly one route per run, and not the same route.

The signature is identical in every case and worth recording, because three plausible explanations
are already eliminated:

- The captured page height oscillates between **5017 px and 5022 px** on consecutive captures inside
  Playwright's own stability check, until it times out. Content is otherwise identical.
- It is **not** DOM instability: sampled every 200 ms for 2.4s under the visual test's exact
  conditions, `scrollHeight` is a constant 5022 on both affected routes.
- It is **not** a viewport-feedback loop from `max-height: 80vh` on `.app-shell-panel`: with the
  viewport driven to 720 / 5017 / 5022 px the document height stays 5022, and the harness already
  overrides that rule to `none` during capture.
- It is **not** the binary difference of defect 4, which is a stable 5px and was eliminated by using
  the headless shell.

What remains is the `fullPage` capture path itself: the image height disagrees with the DOM height
that produced it. This belongs to SPEC-055, which owns the visual harness and its budgets.

**One real case run end to end (deliverable — not executed).** SPEC-037 established that live-model
e2e stays manual and consented because it spends real API usage, and SPEC-056 keeps that out of
scope for everything beyond this single run. It was not run unilaterally. The closest available
evidence is stub mode's full lifecycle — `POST /api/cases` → scope checkpoint → both signatures →
`done`, with artifacts asserted from disk rather than from the screen — which exercises every stage
and both gates but no model latency. The activity-coverage claim is therefore computed from
SPEC-020's recorded real-case profile rather than from a fresh run, as described above.

## Conclusion

The structural promise is verified and narrow: six backend files, every change a read or an emit.
The phase's central UX claim is measured, not asserted, and the measurement is falsifiable — the
instrument has its own tests, and deliberately removing its supersession rule fails two of them.

The phase did not make a three-hour case shorter. It made the waiting legible: from an interface
that could account for at most 6.6% of a real run to one that accounts for at least 93.4% of it.

Two things are honestly outstanding: a one-line product defect that blocks a class of prompts
entirely, and a visual gate that is not yet stable enough to satisfy its own budget.
