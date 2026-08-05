# What consulting firms and think tanks do that this repo does not

**Date:** 2026-08-04
**Scope:** How professional advisory firms actually run a framework-driven engagement — input, process, deliverable — and where AgentAdvisor sits against that standard.
**Method:** Practice research against published standards (ICD 203, RAND QA, the Decision Quality chain, Heuer/Pherson structured analytic techniques, standard engagement management), then a read of the repo's schemas, stages, roles and gates to establish what is genuinely present rather than aspirational.

---

## 1. Executive summary

The repo is already strong on the *middle* of an engagement. Framing, MECE decomposition,
hypothesis-first reasoning, parallel evidence gathering with provenance, adversarial challenge,
pre-mortem, sensitivity analysis, and traceable citation are all built and enforced by
deterministic code. On the analytic-process axis it compares well to professional practice, and in
some respects (four separate uncertainty measures, independence groups, reproducible analysis code)
it is stricter than most consulting output.

The gaps are concentrated at the **two ends** — what goes in, and what comes out.

- **Input.** The entire input surface is one text prompt plus at most five clarification answers
  that can only fill eight enum fields. There is no channel for the user's own documents, no
  weighting of their objectives, and no way to ask them a substantive question. A real engagement
  is dominated by client-internal data; this one cannot see any.
- **Output.** The deliverable ends at `next_actions: list[str]`. There are no owners, no dates, no
  first steps, and nothing that survives delivery. The pre-mortem generates `leading_indicators`
  and the final recommendation generates `recommendation_change_triggers` — both are prose lists
  that no code ever revisits. The engagement ends the moment the report renders.

Measured against the Decision Quality chain — appropriate frame, creative alternatives, reliable
information, clear values and tradeoffs, sound reasoning, commitment to action — the repo scores
well on 1, 2, 3 and 5, has element 4 present only as prose, and has element 6 essentially absent.
The chain is only as strong as its weakest link, which makes elements 4 and 6 the highest-value
targets in the codebase.

---

## 2. How firms actually run a framework engagement

### 2.1 The frameworks themselves

Two distinct things get called "frameworks," and it matters which one is meant.

**Process frameworks** govern how the work is conducted: hypothesis-driven investigation (a
day-one answer that the work then tries to kill), MECE issue trees, the workplan that maps each
branch to a named analysis with an owner and a data source, the "so what?" test applied to every
exhibit, and the Minto pyramid that forces the answer to the top of the document. In the
intelligence and think-tank world the equivalents are the Heuer/Pherson structured analytic
techniques — Analysis of Competing Hypotheses, Key Assumptions Check, Quality of Information
Check, indicators and warning, devil's advocacy, Team A/Team B.

**Content frameworks** are the domain lenses: Porter's five forces, value chain, 7S, TCO models,
DCF, scenario matrices. These are cheap and interchangeable. Firms treat them as vocabulary, not
method — a junior consultant who applies a framework without a hypothesis is doing it wrong.

The repo has adopted the process frameworks (issue tree, provisional thesis, dual-track, challenge,
pre-mortem) and encodes content frameworks as skill packs. That is the correct priority order.

### 2.2 Input, process, deliverable — tidied

| | **Consulting engagement** | **Think tank / analytic shop** |
|---|---|---|
| **Input** | Proposal and engagement letter fixing scope, exclusions, timeline, fee. Kickoff and scoping workshop with the decision maker. **A data request list issued in the first days** — financials, ops data, CRM extracts, contracts, system access. Stakeholder and decision-rights map. Expert-network calls and client-personnel interviews. Customer surveys, site visits. The firm's benchmark database and prior engagement knowledge. | A standing research agenda, not a single question. Systematic literature review of what is already known. Funder identification and disclosure. Datasets, often built in-house and published. Expert convening — roundtables, workshops under Chatham House Rule. An advisory board or steering committee. |
| **Process** | Hypothesis-first, then disprove. Issue tree to workplan with named owners and due dates. **Weekly steering-committee cadence and interim readouts — no surprises at the end.** Internal review ladder: EM daily, Partner weekly. Red-team review before major client meetings. Independent model QA by someone who did not build the model. Storyline and ghost deck drafted *before* the analysis, so the team knows what it must prove. Every exhibit carries a source line and backup. | Formal **peer review by qualified reviewers who are not on the project**, with power to block publication. Explicit analytic standards (ICD 203: describe source quality, express and explain uncertainty, distinguish information from assumption and judgment, **incorporate analysis of alternatives**, demonstrate relevance, use clear argumentation, explain change from prior judgments). Controlled estimative language mapping words to probability bands. Structured techniques applied by name. Base rates and reference classes from stored data. |
| **Deliverable** | Tiered: board one-pager, executive readout deck, full report, appendix. **A live financial model the client keeps and can flex.** Implementation roadmap — 30/60/90, workstreams, owners, dependencies, resourcing. KPI baseline and targets. Risk register with mitigations and owners. Governance design. Capability transfer and training. Sign-off at a final steering committee. | Publication pipeline: working paper → peer review → report → policy brief → op-ed → testimony → briefing. Explicit limitations-of-analysis and conflict-of-interest statements. Published indicators and warning lists that the shop then **tracks over time**. Corrections policy and versioning. A dissemination and engagement plan; publication is the midpoint, not the end. |

The pattern across both columns: the input is *heavily* private and human-sourced; the process has
independent challenge with real authority; and the deliverable is a mobilization instrument with a
life after handover, not a document.

---

## 3. What the repo does today

| | **AgentAdvisor** |
|---|---|
| **Input** | `IntakeRecord.raw_prompt` — a single string. Up to five `ClarificationQuestion`s, each restricted to one of eight `IntakeField` enum values (question, deadline, alternatives, objectives, constraints, risk tolerance, reversibility, depth). `--answers <file.yaml>`. Keyword-selected skill pack. Cross-case memory digest and prior evidence by keyword overlap. **No path for user documents, spreadsheets, contracts, or private data — zero hits for attachment/upload/user_document/internal_data across `orchestrator/`.** |
| **Process** | Ten-plus stages: intake → framing → **gate** → structuring → provisional thesis (dual track) → planning → investigation → evidence critique → assumption ledger → preliminary recommendation → pre-mortem → challenge → repair (≤2) → stop decision → synthesis → review → **gate**. Deterministic budgets, stop rules, schema validation, workspace isolation, stage gates with blocking findings, marginal-value task filter, reviewer verification worksheet. **Exactly two human touchpoints in the entire run.** Reviewer checks citations and calibration coherence; it is a conformance check, not an independent second opinion on the substance. |
| **Deliverable** | One `final_recommendation.md` plus the browsable artifact tree, and a web UI with five inspection rooms. Schema carries recommended action, timing, ranked `alternatives_considered` (rank + prose rationale only), key reasons, scenarios, quantitative findings, counterarguments, critical assumptions, `recommendation_change_triggers: list[str]`, `next_actions: list[str]`, citations, and the four uncertainty measures. `analysis/` holds runnable code. `record_outcome.py` can attach a realized outcome and feeds a Brier score. The `.factory/skills/consulting-deck/` skill can produce a deck by hand, outside the pipeline. |

---

## 4. The gap list

Ordered roughly by how much decision quality is lost.

**Input**

1. **No private evidence channel.** The single largest divergence. A job-offer decision has an
   actual offer letter; an investment has a term sheet and cap table; build-vs-buy has vendor
   quotes and the current spend. The system researches the public web around the decision and never
   reads the decision's own documents.
2. **Objectives are collected and then never used quantitatively.** `objectives: list[NonEmptyStr]`
   enters `DecisionSpec` and never binds to the ranking. `AlternativeAssessment` is
   `{alternative, rank, rationale}` — no per-objective scores, no weights. The README advertises the
   chain "objectives → alternatives → criteria → evidence → … → recommendation"; the objectives link
   is decorative. North star §8's `EU(a) = Σ P(s|E) × U(a,s)` exists in prose only — the analyst may
   emit `expected_values_by_alternative`, but nothing ties that to the user's stated values.
3. **Clarification questions cannot ask anything substantive.** Capped at five and constrained to
   eight enum fields, so intake can ask "what is your risk tolerance?" but not "what is your cost
   basis?" or "what did the vendor quote?"
4. **No stakeholder or decision-rights map.** For any decision involving other people, who must
   agree is not modeled.

**Process**

5. **No independent peer review with authority.** The Reviewer verifies citation integrity and
   confidence coherence. Nobody asks a qualified, independent reviewer "would you reach this
   conclusion from this evidence?" and lets them block. RAND's model is a reviewer who could have
   done the work and is not on the team.
6. **No Analysis of Competing Hypotheses.** Dual-track theses and challenger objections are good,
   but ACH is stronger and the prerequisites are all present: score each evidence item against
   every hypothesis, weight by **diagnosticity** (evidence consistent with all hypotheses proves
   nothing), and prefer the least-disconfirmed hypothesis rather than the best-supported one. This
   is the direct structural antidote to confirmation bias.
7. **Only two human checkpoints.** A three-hour run with no interim readout. Professional practice
   is a weekly steering cadence precisely so direction can be corrected mid-flight.
8. **Nothing red-teams the final package.** The Challenger attacks the preliminary recommendation;
   the synthesized deliverable itself is never attacked.
9. **No estimative-language standard.** Probabilities are numeric and the north star warns against
   false precision, but there is no controlled vocabulary binding words like "likely" to bands.
10. **No reference-class library.** §9 mandates "base rate first," but each agent invents its own
    base rate; none are stored, reused, or checked.
11. **No limitations-of-analysis statement.** `DisclosureRecord` covers stop reasons and exhausted
    budget dimensions only. There is no "here is what we could not assess, where the evidence was
    thin, and what a deeper engagement would have done."

**Deliverable**

12. **`next_actions` is untyped prose.** No owner, date, first step, cost, or dependency. Decision
    Quality element 6 — commitment to action — is absent.
13. **Nothing survives delivery.** `FailureMode.leading_indicators` and
    `recommendation_change_triggers` are exactly the raw material of an indicators-and-warning
    list, generated on every case and then discarded. `record_outcome.py` exists but is manual,
    unprompted, and disconnected from those triggers.
14. **No risk register.** `FailureMode.preventive_action` is generated per failure mode and never
    reaches the deliverable as a tracked register with owners.
15. **One deliverable tier.** A single markdown document serves board-level and analyst-level
    readers alike. The deck skill is manual, post-hoc tooling outside the pipeline.
16. **The model is reproducible but not flexible.** The user can rerun `analysis/`, but cannot
    change an assumption and watch the ranking flip.

---

## 5. Top five high-value changes

### 1. Let the user's own documents into the case — a private evidence channel

**Closes gaps 1, 3.** Highest ceiling of anything on this list, and the change that turns a
web-research bot into an advisor. Add `cases/<id>/inputs/` and an ingestion step at intake that
mints `PrivateEvidenceRecord`s alongside the existing ledger: provenance is file plus page or cell
rather than URL, `source_type: user_document`, directness high, `independence_group` per document,
and an explicit `verifiable: false` so the evidence critic scores it honestly instead of treating it
like a filing. Extend the clarification mechanism so intake can ask for a *document* ("upload the
term sheet") and for free-text substantive facts, not just the eight enum fields. Project private
records into researcher, analyst and director; keep them out of review roles that must not be
anchored, which the existing isolation machinery already supports.

This is the largest build of the five. It is also the one that most improves every downstream
stage at once, because the analyst finally models the real numbers rather than public proxies.

### 2. Make the deliverable a mobilization instrument, and keep the case alive after delivery

**Closes gaps 12, 13, 14.** Best effort-to-value ratio on the list, because most of the content is
already being generated and thrown away.

Type the action plan: `NextAction{action, owner, by_date, first_step, estimated_cost, depends_on,
why_now}`. Then assemble a `MonitoringPlan` deterministically from artifacts that already exist —
every `FailureMode.leading_indicators` entry and every `recommendation_change_triggers` entry
becomes a tracked item with an observable, a threshold, a check cadence, and a statement of which
alternative it would flip to. Surface it as `advisor watch <case-id>` and a Monitoring room in the
UI that lists checks now due, and wire a due check into the existing `record_outcome.py` path so
the Brier loop gets fed by prompting rather than by the user remembering.

This converts a one-shot report into a standing position, which is the behavior SPEC-025 already
argued separates a think tank from a one-off engagement.

### 3. Analysis of Competing Hypotheses as a real stage

**Closes gaps 6, 8, and gives gap 2 somewhere to land.** The repo has every prerequisite: an
evidence ledger with independence groups, a broadened alternative set, and a challenger.

Add an `ACHMatrix` artifact scoring each evidence record against each alternative
(strongly consistent / consistent / neutral / inconsistent / strongly inconsistent), compute
**diagnosticity** deterministically in the orchestrator — an evidence item consistent with every
hypothesis carries zero weight — and rank alternatives by weight of disconfirming evidence rather
than supporting evidence. Run it after evidence critique, before the preliminary recommendation, so
the Director must confront the matrix rather than write around it. Two payoffs beyond rigor: it
produces the single best exhibit in the deliverable, and it finally gives `AlternativeAssessment`
real content instead of rank-plus-prose.

### 4. Independent review with authority, plus an honest limitations statement

**Closes gaps 5, 8, 11.** Replace conformance-only review with the RAND pattern. A reviewer on a
model family different from both the Director and the Challenger receives the final package and the
raw evidence ledger but **not** the reasoning trail, and answers one question: would you reach this
conclusion from this evidence? Disagreement blocks delivery and routes to a repair cycle rather than
being recorded as a note. The existing gate machinery already supports blocking findings, so this
is mostly a role, a projection, and a wiring change.

Pair it with a required `Limitations` section in the deliverable — what could not be assessed, where
evidence was thin or single-sourced, which questions in the issue tree went unanswered (the
`compute_coverage` data already exists), and what a deeper engagement would have done. Every serious
analytic shop publishes this; the repo currently discloses only budget exhaustion.

### 5. Elicit the value model and bind it to the ranking

**Closes gap 2.** Cheapest of the five and it repairs an advertised claim.

At the scope checkpoint, ask the user to weight their objectives — a hundred-point allocation is
enough, swing weighting if you want to be strict — and carry the weights into `DecisionSpec`.
Require `AlternativeAssessment` to carry a score per objective. Then compute the ranking in the
orchestrator from weights and scores, and **compare it against the agent's stated rank**, flagging
divergence as a gate finding. Deterministic code computing expected values over agent-supplied
values and probabilities is exactly the division of labor north star §8 specifies, and it is
currently the section of the north star with the widest gap between text and code.

It also makes sensitivity analysis land where it matters: today the analyst varies model parameters,
but nobody varies *the user's own weights*, which is usually what actually flips a personal decision.

---

## 6. Deliberately not in the top five

- **Interim readout gate.** Real practice, but a three-hour run already has a live activity UI, and
  a third blocking gate adds friction before it adds quality. Worth revisiting once runs are longer
  or more expensive.
- **Storyline-first / Minto discipline in the primary deliverable.** The deck skill covers the
  presentation case, and the markdown report's section order is already close to a pyramid.
- **Estimative-language lexicon and a reference-class library.** Both are right, both are cheap, but
  each is a refinement of a mechanism that already works rather than a missing limb.
- **Deliverable tiering and a flexible model.** Follows naturally once change 2 gives the case a
  post-delivery life; premature before that.
- **Stakeholder and decision-rights map (gap 4).** Real practice, and it matters for any decision
  needing someone else's agreement — a partner, a manager, a board. Deferred because it needs an
  identity model this system does not have and SPEC-041 explicitly declines to introduce, and
  because for a single-user tool the owner is usually the user. Revisit if organizational decisions
  become a common case. *(Added 2026-08-04 during the adversarial review below, which found this gap
  was catalogued in section 4 and then neither specced nor deferred.)*

---

## 7. Implementation cost

### 7.1 The measured unit cost of a stage

Phase 6 (`55b7ded`) is the best available baseline: it added four roles, four stages, the gate
system, the verification worksheet, cross-case memory and five skill packs in one commit —
**6,471 insertions and 65 deletions across 80 files**. The ratio is the important number. This
codebase grows by addition, not by rewrite, because the extension points are registries rather
than conditionals.

Derived cost of one new stage-plus-role, when no existing artifact changes:

| Component | Lines | Note |
|---|---|---|
| `cursor/roles/<role>.md` + `.yaml` | ~80 + ~13 | `test_role_contracts.py` enforces md ↔ schema agreement |
| `orchestrator/artifacts/<name>.py` | 40–100 | `premortem.py` 49, `issue_tree.py` 85, `tracks.py` 38 |
| `schemas/<name>.schema.json` | 100–260 | generated by `make schemas` |
| `frontend/src/generated/<name>.ts` | — | generated by `npm run generate:types`; `check:clean` fails the build on drift |
| Deterministic module | 60–180 | `tracks.py` 71, `issue_tree.py` 57, `evidence_critic.py` 177 |
| `stages.py` handler | ~85 | Phase 6 added 336 lines for four stages |
| `state_machine.py` | ~27 | stage enum, transition set, flow plan |
| `projection.py` | ~25 | one handler function, one `_INCLUDE_HANDLERS` entry |
| `artifacts/__init__.py`, `schema_export.py` | ~25 | export plumbing |
| `stub_backend.py` | ~30 | a `_make_*` fixture, or the stub pipeline tests fail |
| `service/lexicon_data.yaml` | 1–3 entries | unnarrated audit events render as raw technical noise |
| Tests | 150–250 | `test_pipeline_stub.py`, `test_state_machine.py`, one new unit file |
| `caseview.py` + a UI room, if user-visible | ~100 py + ~150 tsx | only if it must be inspectable |

**A new stage and role costs roughly 600–900 lines across ~15 files, essentially all additive.**

### 7.2 What is actually expensive

Not new stages. The expensive categories are:

1. **Changing a required field on a widely-consumed artifact.** The tax is 725 tests, 35 artifact
   fixtures, schema regeneration, TypeScript regeneration behind a drift gate, the
   `test_role_contracts.py` static check, ~178 parametrized coercion tests that walk every field of
   every model, the role `.md` files that must be edited in lockstep, and the frontend components
   and their tests.
   *Mitigation the codebase already supports:* adding an **optional** field with a default breaks
   no fixture and no test. Most of what follows is designed around that.
2. **Changing case lifecycle semantics.** `state_machine.py` is deliberately rigid — one-way
   transitions to terminal states. It is the one module where the repo has chosen inflexibility on
   purpose, so anything that makes a case non-terminal is a genuine architectural change rather
   than an addition.
3. **Adding a dependency.** `AGENTS.md` requires user sign-off.
4. **Touching the evidence provenance model.** `EvidenceRecord` is consumed in 17+ modules and its
   web-shaped required fields (`source_url`, `publisher`, `publication_date`) are load-bearing for
   `normalize.py`, `citations.py`, `evidence_critic.py`, `gates.py` and the domain-keyed source
   reputation in `memory.py`.

### 7.3 The five changes, costed

| # | Change | Difficulty | Est. lines | Files | Breaking? |
|---|---|---|---|---|---|
| 4 | Independent review + limitations | **Easy** | 500–700 | ~12 | No |
| 5 | Bind the value model to the ranking | **Easy–moderate** | 400–600 | ~15 | No, if fields are optional |
| 3 | Analysis of Competing Hypotheses | **Moderate** | 800–1,100 | ~16 | No |
| 2 | Mobilization + post-delivery monitoring | **Hard** | 900–1,400 | ~25 | Yes, one required field + lifecycle |
| 1 | Private evidence channel | **Hardest** | 1,500–2,500 | ~30 | Yes, at the most-depended-on artifact |

**#4 — Easy, and the cheapest per unit of value.** The variant mechanism already exists:
`load_role_config(role, variant)` resolves `reviewer-b` to its own md, yaml and model entry exactly
as `director-b` does today. So this is a role pair, a projection handler that supplies the evidence
ledger while withholding the reasoning trail, ~60 lines of wiring in `handle_review`, a
`backends/*/models.yaml` entry, and an optional verdict field. Blocking already works — the gate
system supports blocking findings and the synthesis retry edge exists. The limitations statement is
one optional field on `FinalRecommendation` plus `render.py` and the synthesizer md. No frontend
work required; the Method and Challenges rooms can absorb it. The real cost is runtime, not code:
one more high-tier invocation per case.

**#5 — Easy to moderate, entirely additive if done carefully.** Add
`objective_weights: dict[str, float] | None` to `DecisionSpec` and
`objective_scores: dict[str, float] | None` to `AlternativeAssessment`. Both optional, so none of
the 35 fixtures or the existing cases break. Then a small deterministic ranking module (~80 lines),
a gate check comparing the computed rank against the agent's stated rank (~40), two role md updates,
and the weighting UI. `objectives` appears in 25 files, but the frontend touchpoint you need is
`ScopeCheckpoint.tsx`, which already renders objectives — the weighting control belongs exactly
there. One specific warning: `dict[str, float]` is the field shape that has already produced a
coercion bug in this repo (`_base_type` misidentifying `dict[str, int]` as `str`), so verify the
property tests actually cover the new fields rather than assuming.

**#3 — Moderate, and a textbook instance of §7.1.** New artifact, new role, new stage, plus a
genuinely interesting deterministic module for diagnosticity scoring (~150–200 lines; the nearest
analogues are `tracks.py` at 71 and `evidence_critic.py` at 177). Nothing existing changes, because
the matrix is its own artifact referencing `E-` IDs and alternative names that already exist. Add
~200 lines of TSX if you want the exhibit, which is most of the payoff.
**The risk here is not code, it is agent reliability.** Filling an N×M consistency matrix is a
harder structured-output task than anything currently asked of any role, the matrix grows with
evidence count (batches cap at 8 records each), and this repo's history shows structured-output
failures are where invocations actually die. Budget for coercion failures and a retry ladder, and
consider capping the matrix to high-materiality evidence.

**#2 — Hard, but the difficulty is concentrated in one half.** Typing `next_actions` is small:
only about eight real code sites (`recommendations.py:57`, `render.py:237`, `caseview.py:702`,
`stub_backend.py:504`, one frontend test, one copy entry, plus fixtures). It is breaking, because
the field is required with `min_length=1`, but the blast radius is contained — call it 250 lines.
Assembling a `MonitoringPlan` deterministically from `FailureMode.leading_indicators` and
`recommendation_change_triggers` is another ~200, and needs no agent call at all.
The expensive half is the lifecycle. The system is built end to end around a case that terminates:
one-way transitions, terminal stages, a CLI and service that assume run-to-completion. A case that
stays open, accrues due checks, and can be re-opened when a trigger fires is a new concept in
`state_machine.py` — the one module where change is deliberately costly. It also forces a product
decision: does a fired trigger re-open the original case, or open a linked new one? That question,
not the code, is the hard part.

**#1 — Hardest, and the difficulty is structural rather than volumetric.** `EvidenceRecord`
requires `source_url`, `publisher` and `publication_date`. A user's offer letter has none of them.
There are three routes and each has a real cost:

- *Make them optional.* Cheapest schema change, worst consequences: it weakens validation for all
  evidence, and the domain-keyed source reputation in `memory.py` plus independence grouping in
  `normalize.py` assume a URL exists.
- *Add a separate `PrivateEvidenceRecord`.* Cleanest semantically, but it must be unioned at 17+
  consumer modules and every place that iterates the ledger.
- *Synthesize a pseudo-URL* (`file://inputs/offer-letter.pdf`). Keeps the model intact and is by
  far the cheapest, at the price of lying to the reputation and independence machinery — acceptable
  only if `source_type` gains a `user_document` member that those two modules explicitly special-case.

On top of the model decision: file parsing (PDF, xlsx, docx — new dependencies, so user sign-off),
an upload endpoint in `service/app.py`, an ingestion stage, a chunking and excerpting strategy so a
40-page PDF does not consume the projection character budget, and an isolation audit — private
documents must reach the analyst and director but must not reach the review roles, which
`build_workspace` and `assert_isolated` can enforce but do not today. `IntakeField` is also a closed
`StrEnum` guarded by a validator asserting that clarifications target unpopulated fields, so
allowing intake to request a *document* means changing that validator's logic, not just adding an
enum member.
There is also a decision worth making explicitly rather than by default: private documents would be
written into agent workspaces and sent to a third-party CLI backend.

**A cheap first cut exists.** Accept markdown and plain text only, synthesize `file://` URLs, add
`SourceType.USER_DOCUMENT`, special-case it in `evidence_critic.py` and `memory.py`, and skip the
upload endpoint by reading whatever the user drops in `cases/<id>/inputs/`. That is perhaps 400
lines, adds no dependencies, and delivers most of the decision-quality gain. The full version can
follow once the seam is proven.

### 7.4 Sequencing

Difficulty runs almost exactly inverse to value, so the cheap changes should go first — and two of
them make the expensive ones easier. **5 → 4 → 3 → 2 → 1.**

Change 5 gives alternatives a typed score, which change 3's matrix can populate rather than invent.
Change 4 establishes a third model family in the role table, which is infrastructure change 3's
matrix scoring would also want. Changes 5, 4 and 3 together are roughly 1,700–2,400 lines and break
nothing — comparable to a third of Phase 6, which was delivered in one commit. Only after those
should the two changes that alter lifecycle semantics and the evidence model be attempted, and each
deserves its own spec.

---

## 8. Adversarial review of the Phase 8 specs (2026-08-04)

Every gap in section 4 was traced to either a spec that closes it or an explicit deferral in
section 6. Three defects were found and fixed; the coverage table below is the result.

| Gap | Coverage |
|---|---|
| 1 Private evidence | SPEC-043 |
| 2 Objectives not quantitative | SPEC-038 |
| 3 Clarifications cannot ask substantive questions | SPEC-043 — **was partial, fixed** |
| 4 No stakeholder map | **Was silently dropped, now deferred in section 6** |
| 5 No independent peer review | SPEC-039 |
| 6 No ACH | SPEC-040 |
| 7 Only two checkpoints | Deferred, section 6 |
| 8 Nothing red-teams the final package | SPEC-039 |
| 9 No estimative-language standard | Deferred, section 6 |
| 10 No reference-class library | Deferred, section 6 |
| 11 No limitations statement | SPEC-039 |
| 12 `next_actions` untyped | SPEC-041 |
| 13 Nothing survives delivery | SPEC-042 |
| 14 No risk register | SPEC-042 — **was missing entirely, fixed** |
| 15 One deliverable tier | Deferred, section 6 |
| 16 Model not flexible | Deferred, section 6 |

**Defect 1 — gap 14 was claimed closed and was not in any spec.** Section 5 states that change 2
"closes gaps 12, 13, 14," but SPEC-042 assembled its plan only from `leading_indicators` and
`recommendation_change_triggers`. `FailureMode.preventive_action` — the entire basis of gap 14 —
appeared in no spec in the phase. The error came from treating the pre-mortem as a source of
*indicators* and forgetting it is equally a source of *responses*. SPEC-042 now carries
`TrackedMitigation`, linked by `triggered_by` to the indicators from the same failure mode, so a
breach surfaces the observation and the prepared response together.

**Defect 2 — gap 3 was half-covered.** SPEC-043 relaxed the intake validator so a clarification
could request a *document*, but gap 3's own examples are free-text facts ("what is your cost
basis?", "what did the vendor quote?"), and section 5 change 1 explicitly promised both. Facts that
decide personal cases usually live in the user's head, not in a file. SPEC-043 now adds
`ClarificationKind` (`field` | `document` | `fact`), makes `resolves_field` required only for
`field`, raises the cap from 5 to 8, and records `fact` answers as user-supplied evidence with the
same `unverifiable` treatment as a document rather than promoting them to fact.

**Defect 3 — gap 4 vanished between sections.** The stakeholder and decision-rights map was
catalogued in section 4 and then neither promoted to a spec nor listed among the deliberate
deferrals, so it disappeared without a decision. Now deferred explicitly, with the reason.

**Two smaller corrections.** SPEC-038 and SPEC-042 emit audit events but did not schedule
`lexicon_data.yaml` entries; unnarrated events render through the unknown-event fallback, so both
specs now list them with an acceptance criterion. SPEC-040 described ACH's mechanics without citing
Heuer and Pherson or noting that analysis of alternatives is one of ICD 203's nine tradecraft
standards — an implementer writing the role instructions benefits from the source.

**Research coverage.** The ICD 203 tradecraft standards map onto the pipeline as follows: source
quality description (evidence critic, SPEC-023), uncertainty expression (four separate measures),
distinguishing information from assumption (assumption ledger, SPEC-023), **analysis of
alternatives (SPEC-040, previously absent)**, customer relevance and implications (SPEC-041),
explaining change in judgments (thesis revision ledger, SPEC-024), accuracy over time (Brier
calibration, SPEC-025), and visual information (SPEC-040's exhibit). The Heuer/Pherson techniques
surveyed are similarly accounted for: ACH (SPEC-040), Key Assumptions Check (SPEC-023), Quality of
Information Check (SPEC-023), indicators and warning (SPEC-042), devil's advocacy and Team A/Team B
(challenger and dual-track, SPEC-024). The Decision Quality chain's weak links — element 4 and
element 6 — are SPEC-038 and SPEC-041/042 respectively.

**One research finding remains unimplemented by design.** Consulting practice issues a *data
request list* at kickoff: the firm tells the client which documents it needs. SPEC-043 approaches
this from the other end — the user supplies what they have, and intake may request a specific
document when it notices a gap. A generated, upfront request list is the sharper version and is a
reasonable follow-on once SPEC-043 shows what intake actually asks for in practice.
