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
