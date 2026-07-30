# Decision Intelligence Platform — North Star

**Status:** Product and architecture direction  
**Audience:** Coding agents and future maintainers  
**Project type:** Personal project  
**Last updated:** 2026-07-30

---

## 1. Purpose of this document

This document defines the product intent, conceptual architecture, operating principles, and major decisions for a personal multi-agent decision-intelligence platform.

It is deliberately not a technical implementation specification. It should guide implementation choices without fixing the project prematurely to a particular framework, database, model, or interface.

The coding agent should treat this document as the product's north star. When implementation choices conflict, prefer the choice that best preserves:

1. decision quality;
2. traceability from evidence to recommendation;
3. disciplined handling of uncertainty;
4. context isolation between agents;
5. simplicity appropriate for a personal project; and
6. the ability to change model providers later.

---

## 2. Product thesis

Most research-oriented AI products are optimized to answer questions such as:

> What is true, what happened, or why did it happen?

This platform is optimized for a different question:

> Given an imperfectly defined situation, what should I do, why, under what assumptions, and with what degree of uncertainty?

The platform should behave less like a search assistant and more like a small consulting team, investment committee, or internal strategy unit.

The user may begin with an ambiguous prompt such as:

- Should I invest in company AAA?
- Should I accept this job offer?
- Should I build or buy this software capability?
- Which market should a company enter?
- Should I relocate to one of several countries?
- Which technical architecture should I choose?

The system should transform that prompt into a structured decision process. It should identify the actual decision, expose missing alternatives, define relevant criteria, collect evidence, perform quantitative analysis where useful, challenge its own conclusions, and return a recommendation that is explicit about uncertainty.

---

## 3. Product promise

For each decision, the platform should produce:

1. a clear formulation of the decision;
2. the realistic alternatives, including options the user did not initially mention;
3. the user's objectives, constraints, time horizon, and risk preferences;
4. the material facts and evidence;
5. the assumptions required to bridge evidence gaps;
6. quantitative scenarios or models where appropriate;
7. the strongest arguments for and against each leading alternative;
8. a recommended action;
9. probability or confidence estimates with an explanation of what they mean;
10. the conditions under which the recommendation would change;
11. practical next actions; and
12. citations linking major factual claims to their sources.

The primary differentiator is not that the platform uses multiple agents. The differentiator is the inspectable chain:

> user objective → alternatives → criteria → evidence → assumptions → scenarios → objections → recommendation

---

## 4. What the product is not

The product is not:

- a generic multi-agent chat room;
- an unrestricted debate between language models;
- a model-voting system;
- a conventional deep-research report with a recommendation appended at the end;
- a system that invents precise probabilities without a defensible basis;
- a replacement for regulated professional advice;
- a fully autonomous actor that executes consequential decisions without user approval;
- a general-purpose production SaaS in its first form; or
- a showcase whose complexity exists mainly to demonstrate many agents.

Adding more agents is not inherently an improvement. Every role must have a distinct epistemic or operational purpose.

---

## 5. Core design principles

### 5.1 Decision first, research second

Research must be driven by the decision model. The system should not collect information merely because it is interesting or adjacent to the topic.

Every research or analysis task should answer at least one of these questions:

- Could this evidence change the ranking of the alternatives?
- Could it materially change an outcome probability?
- Could it expose a major risk or omitted alternative?
- Could it reduce an uncertainty that matters to the user's action?

### 5.2 Structured artifacts over shared conversation history

Agents should communicate through typed, concise artifacts rather than inheriting the full transcript of every other agent.

This reduces context rot, accidental anchoring, duplicated reasoning, and leakage of irrelevant material.

### 5.3 Controlled disagreement over theatrical debate

The platform should create genuine adversarial review, but should avoid endless back-and-forth discussion.

A preferred pattern is:

1. produce a provisional thesis;
2. identify its most material weaknesses;
3. commission targeted work to resolve those weaknesses;
4. update the thesis;
5. perform a final falsification pass; and
6. synthesize the decision.

### 5.4 Deterministic control around probabilistic workers

Language models may propose plans, conduct research, interpret evidence, write code, and synthesize findings. Deterministic application logic should control:

- workflow state;
- task status;
- iteration limits;
- concurrency;
- required schemas;
- validation;
- retry limits;
- stopping rules;
- file access boundaries; and
- user approval gates.

The Planner may recommend what to do next, but the orchestrator decides what is actually executed.

### 5.5 Quantification where useful, not where decorative

The system should use calculations, simulations, scenario models, and sensitivity analyses when they improve the decision. It should not produce numerical precision merely to appear rigorous.

### 5.6 Explicit uncertainty

The platform must distinguish among:

- probability of an external outcome;
- confidence in the evidence;
- confidence in the recommendation;
- sensitivity of the recommendation to assumptions; and
- agreement or disagreement among models.

These are different quantities and must not be collapsed into one percentage.

### 5.7 Evidence provenance is part of the product

Research output should preserve source identity, publication date, retrieval date, relevant excerpt or claim, and limitations. Ten articles derived from one press release do not count as ten independent sources.

### 5.8 Simple first, extensible later

This is a personal project. The initial system should favor a legible local architecture over distributed infrastructure or enterprise abstractions.

At the same time, model execution should sit behind an interface so that Cursor CLI can later be supplemented or replaced by direct APIs without altering the core decision workflow.

---

## 6. Conceptual agent organization

The system consists of a small control layer, temporary worker agents, and final review roles.

### 6.1 Decision Director

The Decision Director owns the substantive decision.

Responsibilities:

- define the decision question;
- identify viable alternatives;
- clarify objectives and constraints;
- maintain a provisional thesis;
- interpret how evidence affects the decision;
- decide which uncertainties are material; and
- produce the preliminary recommendation package.

The Director should not be the sole planner, researcher, or final judge of its own work.

### 6.2 Planner / Orchestrator Adviser

The Planner determines what work remains.

Responsibilities:

- decompose the decision into investigation areas;
- construct and update the task dependency graph;
- identify missing evidence and analysis;
- prioritize work by expected decision value;
- propose targeted follow-up tasks; and
- recommend when further investigation is unlikely to change the conclusion.

The Planner proposes tasks. Deterministic orchestration code enforces budgets and launches workers.

### 6.3 Challenger

The Challenger is an adversarial counterpart to the Director and should normally use a different model family.

Responsibilities:

- identify hidden assumptions;
- find contrary evidence;
- expose omitted alternatives;
- test for confirmation, selection, survivorship, and incentive biases;
- identify tail risks;
- determine which assumptions carry the recommendation; and
- state what evidence would reverse the conclusion.

The Challenger should return a limited number of material objections rather than an unlimited catalogue of possible concerns.

### 6.4 Process Auditor / Steerer

The Auditor protects the process from drift and waste.

Responsibilities:

- compare current work with the original decision;
- flag irrelevant rabbit holes;
- detect duplicated tasks;
- check whether outputs satisfy their schemas and mandates;
- identify unsupported claims;
- enforce stopping conditions; and
- recommend escalation to a stronger model only when justified.

This role should be relatively inexpensive and heavily constrained.

### 6.5 Researcher

Researchers are temporary workers assigned narrow questions.

Responsibilities:

- search for relevant external information;
- prefer primary and authoritative sources;
- distinguish reported fact from interpretation;
- capture source provenance;
- note contradictory evidence and limitations; and
- return structured evidence records rather than narrative essays.

Multiple Researchers may run in parallel, each with an isolated context.

### 6.6 Quantitative Analyst

The Analyst handles computation and model-based analysis.

Responsibilities:

- construct scenario models;
- calculate expected values or ranges;
- perform sensitivity analysis;
- run simulations where justified;
- test break-even conditions;
- make assumptions explicit; and
- save reproducible analysis artifacts.

The Analyst should execute calculations in an actual computational environment. It should not rely on unsupported arithmetic embedded in prose.

### 6.7 Domain Specialist

Domain Specialists are dynamically spawned when the decision requires expertise not adequately represented by the generic roles.

Examples include:

- investment and valuation;
- regulation and legal risk;
- market strategy;
- software architecture;
- scientific evidence;
- security; or
- operations.

These should be task-specific workers or skill packages, not permanent participants in every decision.

### 6.8 Final Synthesizer

The Synthesizer receives the normalized decision package after the challenge and repair cycles.

Responsibilities:

- integrate evidence, analysis, objections, and user preferences;
- avoid simply averaging agent opinions;
- explain why one alternative dominates;
- report unresolved uncertainty;
- state what would change the recommendation; and
- produce the final user-facing document.

### 6.9 Calibration and Citation Review

These may initially be implemented as one final review role.

Responsibilities:

- inspect probability claims for false precision;
- verify that confidence language matches the available evidence;
- ensure major factual claims have valid citations;
- identify source dependence or duplicated provenance; and
- confirm that the final recommendation accurately reflects the underlying artifacts.

---

## 7. Shared decision state

The platform should maintain a structured blackboard for each case.

Conceptually, it contains:

- **Decision specification:** the question, owner, deadline, alternatives, constraints, objectives, and risk preferences;
- **Task graph:** planned, active, completed, blocked, and cancelled tasks;
- **Evidence ledger:** sourced factual records and their limitations;
- **Assumption registry:** explicit assumptions, estimates, confidence, and materiality;
- **Analysis artifacts:** models, calculations, scenarios, and sensitivity results;
- **Objection registry:** challenges, their materiality, and resolution status;
- **Current thesis:** the provisional recommendation and its rationale;
- **Audit log:** important workflow events and decisions; and
- **Final recommendation:** the user-facing output and supporting structured record.

No agent should automatically receive the entire blackboard. The orchestrator should project only the relevant subset into each role's context.

### 7.1 Illustrative artifact shapes

The exact schemas should be defined and versioned in code. The shapes below indicate the intended granularity, not a frozen format.

**Decision specification**

```yaml
decision_id: case-001
decision_question: Should the user invest in AAA?
decision_owner: user
decision_deadline: 2026-08-15
alternatives:
  - invest_now
  - invest_smaller_amount
  - invest_in_stages
  - wait_for_milestone
  - do_not_invest
objectives:
  - expected_return
  - downside_protection
  - liquidity
constraints:
  - maximum_acceptable_loss
  - required_liquidity_horizon
risk_tolerance: moderate
reversibility: partially_reversible
depth_requested: standard
```

**Evidence record**

```yaml
evidence_id: E-102
claim_supported: Market demand grew 18% in 2025
source_title: ...
publisher: ...
source_url: ...
source_type: regulatory_filing
publication_date: 2026-03-12
retrieved_at: 2026-07-29
excerpt: ...
reliability: high
directness: high
independence_group: company_filing
limitations:
  - company-defined market boundary
retrieved_by: researcher-market
```

The `independence_group` field exists so the system can detect when many citations share one underlying origin. Ten articles repeating the same press release are one source, not ten.

**Assumption record**

```yaml
assumption_id: A-017
claim: AAA can reach 5 billion JPY annual revenue within five years
type: forecast
current_estimate: "0.35 probability"
confidence: low
materiality: high
evidence_for: [E-102]
evidence_against: [E-117]
status: unresolved
```

**Objection record**

```yaml
objection_id: O-004
target: preliminary_recommendation_v2
claim: The valuation model assumes uncontested market leadership
materiality: high
evidence_or_reasoning: ...
resolution_status: open
commissioned_tasks: [T-031]
```

**Task record**

```yaml
task_id: T-021
role: researcher
question: What is the realistic competitive response within 24 months?
why_it_matters: Could reverse the ranking between invest_now and wait_for_milestone
expected_information_gain: high
materiality: high
inputs: [decision_spec, E-102, E-117]
required_output: evidence_records
completion_criteria: Primary or high-quality secondary sourcing for the two named competitors
status: planned
```

Stable identifier prefixes (`E-`, `A-`, `T-`, `O-`) allow evidence, assumptions, tasks, and objections to reference each other, which is what makes the final recommendation traceable.

### 7.2 Context projection

Each role invocation receives a projection of the blackboard, never the blackboard itself. Conceptually:

```
context = project(
    state,
    role="challenger",
    include=[
        "decision_spec",
        "preliminary_recommendation",
        "high_materiality_assumptions",
        "key_evidence",
    ],
    token_budget=...,
)
```

The orchestrator, not the agent, decides what is included. No agent receives another agent's raw transcript.

### 7.3 File-based blackboard for the MVP

For the personal MVP, the blackboard can be a structured case directory rather than a database:

```
cases/case-001/
├── shared/
│   ├── decision_spec.yaml
│   ├── evidence/            # one file per evidence record
│   ├── assumptions/         # one file per assumption record
│   ├── objections/
│   └── task_graph.yaml
├── agents/                  # isolated per-invocation working directories
│   ├── planner/
│   ├── director/
│   ├── challenger/
│   ├── researcher-*/
│   ├── analyst/
│   └── auditor/
├── analysis/                # reproducible code, data, and outputs
└── outputs/
    ├── preliminary_recommendation.yaml
    ├── challenge.yaml
    └── final_recommendation.md
```

Plain files keep the system inspectable and diffable, suit a coding-agent harness that reads and writes files natively, and can be replaced by SQLite or PostgreSQL later without changing the conceptual model.

---

## 8. Decision workflow

### Stage 1 — Intake

The platform extracts or asks for:

- the decision to be made;
- why the decision matters;
- the deadline;
- alternatives already considered;
- objectives and constraints;
- time horizon;
- risk tolerance;
- reversibility;
- available internal information; and
- desired depth of analysis.

The system should avoid a long questionnaire where reasonable assumptions would suffice, but it should surface assumptions that materially affect the outcome.

### Stage 2 — Decision framing

The Director produces an initial decision specification and broadens the alternative set.

For example, an investment decision should not be limited to “invest” and “do not invest.” Other alternatives may include:

- invest a smaller amount;
- invest in stages;
- wait for a milestone;
- negotiate different terms;
- seek exposure through another vehicle; or
- decline but revisit later.

### Stage 3 — Provisional thesis

The Director forms a preliminary view based on current information. This prevents research from becoming directionless and gives the Challenger a concrete thesis to test.

The provisional thesis is not presented as the final answer.

### Stage 4 — Investigation planning

The Planner produces a dependency-aware task graph. Each proposed task should include:

- the question to answer;
- why it matters to the decision;
- expected information gain;
- materiality;
- required worker or tool;
- input artifacts;
- required output format; and
- completion criteria.

Tasks should be prioritized approximately by:

> decision materiality × probability that the work changes the conclusion ÷ expected cost

### Stage 5 — Parallel evidence and analysis

Temporary Researchers, Analysts, and Specialists execute narrow assignments in isolated contexts.

Each worker receives only:

- the decision specification;
- its exact task;
- the existing artifacts relevant to that task; and
- the required output schema.

Workers do not receive the conversation history of any other agent.

Their outputs are normalized into the evidence ledger, assumption registry, and analysis artifacts. Normalization should be partly deterministic and should:

- validate each output against its schema;
- deduplicate sources and assign independence groups;
- separate reported fact from interpretation;
- flag stale or superseded data;
- record contradictions between evidence items; and
- reject outputs that do not satisfy their mandate rather than silently accepting them.

### Stage 6 — Preliminary recommendation

The Director updates the thesis and produces a structured preliminary recommendation including:

- preferred alternative;
- current rationale;
- key assumptions;
- estimated outcomes;
- confidence level;
- unresolved evidence gaps; and
- major risks.

### Stage 7 — Adversarial review

The Challenger identifies the few objections most likely to reverse or materially weaken the recommendation.

The Auditor checks whether the challenge is relevant and whether additional work is justified.

### Stage 8 — Targeted repair

The Planner commissions only the work required to resolve material objections. The system should avoid restarting the entire research process.

The initial product should permit a small fixed number of repair cycles, normally one or two.

### Stage 9 — Stop decision

The system stops when one or more of the following is true:

- no critical evidence gaps remain;
- the recommendation is stable across plausible sensitivity ranges;
- no unresolved objection is likely to change the decision;
- expected value of more research is low;
- the investigation budget is exhausted; or
- the user-imposed deadline or depth limit has been reached.

Stopping because of budget or incomplete evidence must be disclosed in the final output.

### Stage 10 — Synthesis and review

The Synthesizer produces the recommendation. Calibration and citation review then inspect the result before it is shown to the user.

### Underlying decision model

Synthesis should rest on an explicit, if simple, decision model rather than holistic prose judgment. Conceptually:

> EU(a) = Σ over scenarios s of P(s | E) × U(a, s)

where `a` is an alternative, `s` is a future scenario, `P(s | E)` is the estimated probability of that scenario given the evidence, and `U(a, s)` is the user-specific value of choosing `a` under `s`.

For an investment decision, the scenario set typically includes bull, base, bear, and failure cases, plus decision-specific factors such as liquidity-event timing, dilution, and opportunity cost.

The division of labor is deliberate:

- language models help define the scenarios, assumptions, and value judgments; and
- deterministic code computes the expected values, thresholds, and sensitivities.

The model is a discipline device. It forces probabilities, values, and assumptions to be stated explicitly and makes sensitivity analysis possible. It is not a claim of numerical objectivity, and the final output should not present it as one.

---

## 9. Probability and confidence policy

The system must never infer an outcome probability solely from agent voting.

If four out of five models agree, that indicates model agreement under those prompts and contexts. It does not establish an 80% probability that the recommendation is correct.

The platform should report distinct measures where applicable:

### Outcome probability

The estimated probability that a future state or event occurs.

Example: probability that an investment produces a positive return within five years.

### Evidence confidence

How reliable, direct, independent, current, and complete the supporting evidence appears.

### Recommendation confidence

How strongly the available evidence and the user's preferences support the preferred alternative over the others.

### Model stability

How often the preferred alternative remains unchanged when assumptions, models, or plausible parameter values vary.

### Reporting example

The distinct measures should appear separately in the structured output, for example:

```yaml
recommended_action: invest_smaller_amount
recommendation_confidence: 0.74      # structured subjective estimate
evidence_confidence: 0.61
outcome_probabilities:
  positive_return_within_5y: 0.58
  total_loss: 0.19
model_stability:
  share_of_sensitivity_runs_supporting_recommendation: 0.76
```

Presenting any one of these numbers as if it were the others is a defect.

### Probability construction

Probability estimates should use, where available:

- relevant historical base rates;
- explicit reference classes;
- documented adjustments from the base rate;
- quantitative scenarios;
- interval estimates;
- simulation;
- sensitivity analysis; and
- historical calibration of prior forecasts.

The intended discipline is base rate first: begin from a reference-class prior, then record each documented adjustment together with the evidence record that motivated it. This gives every probability an audit trail from prior to posterior instead of a single unexplained number.

Before sufficient calibration data exists, probabilities should be described as structured subjective estimates. Weak evidence should normally produce ranges, such as 40–60%, rather than spurious precision such as 51.7%.

---

## 10. Research and citation policy

Research quality is central to the product.

Each material evidence item should preserve:

- the claim it supports or contradicts;
- source title and publisher;
- source URL or stable identifier;
- publication date;
- retrieval date;
- source type;
- relevant excerpt or structured summary;
- reliability and directness assessment;
- limitations;
- whether it is independent from other sources; and
- the agent or tool that retrieved it.

Preferred source order generally is:

1. primary records, filings, official statistics, laws, standards, and original research;
2. highly reputable secondary analysis;
3. specialist reporting or databases;
4. other sources used cautiously and labelled appropriately.

The system should detect when multiple sources share the same underlying origin. Citation quantity is not a substitute for independent evidence.

The final output should place citations next to the claims they support, not only in a bibliography.

---

## 11. Chosen execution approach

### Decision: use Cursor CLI as the initial agent harness

The initial project will use Cursor CLI rather than introducing OpenCode and OpenRouter at the outset.

Reasons:

1. The project is personal rather than a public multi-user service.
2. The user already has a Cursor subscription, making the initial marginal cost low.
3. Cursor CLI supports terminal-based agent use and headless automation.
4. Cursor provides access to multiple frontier models within the Cursor environment.
5. Cursor already offers the primary capabilities needed by the workers: repository context, file operations, command execution, MCP integration, skills, and agent tooling.
6. The Quantitative Analyst benefits especially from a coding-agent harness capable of writing and executing analysis code.
7. Using one familiar harness reduces initial infrastructure and implementation burden.

Cursor is therefore considered both the initial development environment and the initial runtime for personal decision cases.

### Why OpenRouter is not initially required

OpenRouter is valuable as a unified inference API with a broad model catalogue, explicit per-request model control, usage accounting, and provider routing. However, for this personal MVP it would introduce additional token-based cost and integration work before the core product hypothesis has been validated.

The immediate question is not whether the platform can scale across hundreds of models. It is whether a disciplined multi-role workflow produces materially better decisions than a single research agent.

### Important boundary

Cursor CLI is an agent runtime, not a neutral model API. It may internally manage context, tools, and multi-step behavior. The implementation should therefore avoid making core decision logic dependent on undocumented Cursor-specific behavior.

Compared with a direct inference API, this also means less control over exact request messages, sampling parameters, structured-output enforcement, and per-request metadata. For a personal prototype this is acceptable; it is one reason the backend boundary below exists.

A personal Cursor subscription is a personal development tool. Do not assume it can serve as the inference backend for requests from other users without verifying Cursor's current commercial terms.

### Backend abstraction

The conceptual platform should define a generic agent-execution boundary. A role invocation should be expressible in terms of:

- role;
- model preference;
- task instructions;
- allowed tools;
- input artifacts;
- output schema;
- context budget;
- execution budget; and
- result metadata.

Cursor CLI will be the first backend. A future direct-API or OpenRouter backend should be addable without changing the decision state or workflow semantics.

Conceptually:

```
class AgentBackend:
    def run(self, invocation: RoleInvocation) -> RoleResult: ...

class CursorCLIBackend(AgentBackend): ...
# later, without workflow changes:
# class DirectAPIBackend(AgentBackend): ...
```

### Thin deterministic orchestrator

The orchestrator is ordinary application code, not another agent:

```
while not state.finished:
    step = route(state)            # deterministic routing
    result = execute(step)         # may invoke an agent backend
    state = reduce(state, result)  # validated state transition
    checkpoint(state)
```

It owns workflow state, agent spawning, iteration caps, model assignment, budget enforcement, schema validation, retries, human approval gates, and final artifact collection.

Cursor CLI invocations should be headless subprocess calls that read their inputs from files in an assigned working directory and write validated artifacts back. Exact CLI flags, headless behavior, and available models must be verified against the installed version and current documentation (Section 24) rather than assumed.

Do not build the orchestrator as a Cursor agent that manages other agents. That reintroduces exactly the context and control problems this architecture exists to avoid. Similarly, a dedicated workflow framework such as LangGraph is not needed initially; the first workflow is well defined enough for a small custom state machine, and a framework should be adopted only if durable pause and resume, complex conditional branching, or distributed workers become real requirements.

### Workspace isolation

Every agent invocation runs in its own working directory under the case folder. Concurrent invocations must never share mutable files; shared state changes only through the orchestrator's normalization step. Whether concurrent Cursor CLI sessions interfere with one another is an open question (Section 21) and should be tested early.

### Phased execution roadmap

**Phase 1 — Cursor-only prototype.** Python orchestrator, Cursor CLI backend, file-based case blackboard, optionally a small SQLite index. Goals: validate that role separation improves decisions, stabilize artifact schemas, measure actual usage per decision, test Director–Challenger model diversity, and build benchmark cases.

**Phase 2 — Hybrid.** Keep Cursor CLI for the Quantitative Analyst and tool-heavy research, where the coding harness adds the most value. Move roles that need exact prompts, sampling control, and strictly typed outputs, such as the Planner, Auditor, and possibly Director, Challenger, and Synthesizer, to direct APIs or OpenRouter behind the same backend boundary.

**Phase 3 — Production hardening, only if ever needed.** Replace the coding-agent harness in the runtime path with direct model APIs, an owned tool layer, sandboxed execution, and a durable workflow engine. This phase is explicitly out of scope for the MVP and should not shape early code.

---

## 12. Model allocation strategy

Models should be selected by task characteristics rather than by the desire to maximize model diversity.

Model diversity is most important where correlated reasoning errors would be dangerous, especially between:

- Director and Challenger;
- primary analysis and independent review; and
- recommendation synthesis and citation/calibration review.

A typical allocation concept is:

- **Planner:** efficient model with strong instruction following and structured output;
- **Director:** strong reasoning and synthesis model;
- **Challenger:** strong model from a different family than the Director;
- **Researchers:** efficient models with good tool use and extraction;
- **Analyst:** model strong in coding, quantitative reasoning, and iterative tool use;
- **Auditor:** inexpensive model with good constraint adherence;
- **Synthesizer:** strongest appropriate model available; and
- **Citation/calibration reviewer:** precise model with good evidence-grounded checking.

The system should permit the user to alter these assignments, but good defaults matter more than extensive configuration.

Viewed by task rather than by role, the allocation looks like this:

| Task | Requirement | Cost tier |
|---|---|---|
| Intake extraction | reliable structured output | low |
| Investigation planning | instruction following, moderate reasoning | medium |
| Research query generation | fast, broad language ability | low |
| Evidence extraction | accurate schema adherence | low |
| Quantitative analysis | coding and iterative tool-use reliability | medium to high |
| Decision thesis (Director) | strong synthesis and judgment | high |
| Adversarial review (Challenger) | different model family from the Director | high |
| Process auditing | constraint adherence | low |
| Citation and calibration review | precise evidence-grounded checking | medium |
| Final synthesis | strongest available | high |

Using a different model for every agent merely because there are many agents adds complexity without adding epistemic diversity. Diversity matters at the specific boundaries listed above, and nowhere else by default.

---

## 13. Cost and resource principles

Although Cursor offers subscription-based access, the platform should not treat agent usage as free or unlimited.

A single visible agent invocation may perform multiple model and tool turns. A multi-agent workflow can consume included usage rapidly.

Every decision case should therefore have explicit limits such as:

- maximum total agent invocations;
- maximum concurrent workers;
- maximum iterations;
- maximum research tasks;
- maximum high-capability model calls;
- maximum wall-clock execution period;
- per-agent context limits; and
- optional monetary or usage budget where available.

Use the least expensive capable model for extraction, validation, classification, and process auditing. Escalate to stronger models for substantive judgment, difficult analysis, adversarial review, and final synthesis.

The platform should display or record enough usage metadata to compare decision quality with resource consumption.

### Illustrative per-case budget

```yaml
budget:
  maximum_agent_invocations: 40
  maximum_concurrent_workers: 3
  maximum_repair_cycles: 2
  maximum_research_tasks: 15
  maximum_high_tier_calls: 6
  maximum_wall_clock: 2h
```

The numbers are starting points to be tuned against measured usage, but the caps themselves are mandatory and enforced by the orchestrator, not by agent self-restraint.

### Escalation ladder

Run the cheapest capable model first. If an output fails validation, retry once at the same tier, then escalate one tier. Reserve frontier-tier calls for the Director, the Challenger, the Synthesizer, and cases the Auditor explicitly flags as high stakes.

### Marginal-value rule for additional research

Do not launch another worker unless:

> (probability the work changes the decision) × (decision materiality) > (expected cost of the work)

The Planner estimates these quantities; the orchestrator enforces the rule together with the hard caps above.

---

## 14. Human role and approval boundaries

The user is the decision owner.

The platform may:

- clarify the decision;
- suggest omitted alternatives;
- collect evidence;
- construct models;
- rank alternatives;
- recommend actions; and
- propose next steps.

The platform should require user approval before:

- executing financial transactions;
- sending external communications;
- modifying important systems;
- accepting contractual commitments;
- publishing material publicly; or
- taking other consequential external actions.

The initial project should focus on recommendation generation, not autonomous execution.

---

## 15. User experience north star

The experience should feel like commissioning a compact, transparent consulting engagement—not operating an agent framework.

The user should not need to manage seven agents manually.

A preferred interaction is:

1. user states a decision problem;
2. platform presents its interpretation, alternatives, and any critical clarifications;
3. user approves or adjusts the framing;
4. platform shows a concise investigation plan;
5. agents work while the interface exposes meaningful progress rather than raw chain-of-thought;
6. platform flags material uncertainties or requests data only when necessary;
7. user receives the recommendation package; and
8. user can inspect evidence, assumptions, analysis, objections, and sensitivity behind it.

The interface should distinguish clearly between:

- sourced facts;
- agent interpretation;
- user-supplied information;
- assumptions;
- calculations; and
- recommendations.

---

## 16. Final recommendation format

A final decision output should normally contain:

### Executive recommendation

A direct statement of the recommended action and timing.

### Decision confidence

A concise explanation of recommendation confidence, evidence confidence, and major uncertainty.

### Alternatives considered

The serious alternatives and why they rank above or below one another.

### Key reasons

The small number of factors carrying the conclusion.

### Scenario analysis

Relevant upside, base, downside, and tail-risk scenarios, including probabilities or ranges where defensible.

### Quantitative findings

Expected values, thresholds, simulations, or sensitivity results where useful.

### Strongest counterarguments

The material objections and how they were resolved or why they remain unresolved.

### Critical assumptions

The assumptions that materially affect the recommendation.

### What would change the recommendation

Observable events, evidence, prices, terms, or thresholds that would cause a different action.

### Next actions

Concrete steps, ordered by urgency or information value.

### Evidence and citations

Inline citations and an inspectable evidence ledger.

---

## 17. Initial scope

The platform substrate may be general, but the first complete workflow should focus on a bounded class of decisions.

A strong initial vertical is an investment-style decision because it naturally exercises:

- ambiguous framing;
- alternative generation;
- web research;
- source quality assessment;
- quantitative modeling;
- uncertainty;
- adversarial analysis;
- explicit risk tolerance; and
- recommendation thresholds.

The first version does not need to support every domain equally well. A high-quality vertical workflow is preferable to a shallow universal system.

### The first workflow, concretely

1. The user provides the company or asset, the terms, and the decision context.
2. The system generates the decision specification and a broadened alternative set.
3. The user approves or edits the framing and the key assumptions.
4. The Planner creates the investigation task graph.
5. Researchers collect evidence in parallel.
6. The Analyst builds the scenario and sensitivity model.
7. The Director produces the preliminary recommendation.
8. The Challenger attacks it.
9. At most two targeted repair cycles run.
10. The Synthesizer, followed by calibration and citation review, produces the final package.

Different decision domains require different objective functions, evidence standards, reference classes, and quantitative models. The platform substrate stays general; the first decision pack is investment-specific.

---

## 18. MVP success criteria

The MVP succeeds when it can take a real decision prompt and reliably produce a recommendation package that is better than a single-agent baseline in the following dimensions:

### Decision completeness

- identifies omitted alternatives;
- captures objectives and constraints;
- recognizes material uncertainties; and
- states what information is missing.

### Evidence quality

- uses authoritative sources where available;
- attaches citations to material claims;
- records source limitations; and
- avoids treating repeated secondary coverage as independent confirmation.

### Analytical quality

- performs reproducible quantitative work where appropriate;
- distinguishes assumptions from facts;
- exposes sensitivity to material variables; and
- avoids false precision.

### Adversarial robustness

- identifies credible counterarguments;
- can revise its preliminary thesis when contradictory evidence appears; and
- does not merely manufacture disagreement for appearance.

### Relevance and efficiency

- remains tied to the original decision;
- limits low-value rabbit holes;
- stops when more research is unlikely to change the recommendation; and
- remains usable within the user's Cursor subscription and personal computing environment.

### Traceability

- allows the user to inspect why the recommendation was reached;
- connects important conclusions to evidence and assumptions; and
- preserves enough artifacts to reproduce or audit the case.

---

## 19. Evaluation strategy

The project should maintain a set of benchmark decision cases.

Each case should be run through:

1. a single strong-agent baseline;
2. the structured multi-agent workflow; and
3. selected workflow variations.

Evaluation should examine:

- factual accuracy;
- source quality;
- missing alternatives;
- quantitative correctness;
- sensitivity awareness;
- strength of counterarguments;
- recommendation usefulness;
- consistency across repeated runs;
- cost or included usage consumed; and
- human preference after inspecting the reasoning artifacts.

Where decisions later produce observable outcomes, the project should retain forecasts and calculate calibration metrics such as Brier scores. The system should not claim calibrated probabilities until sufficient historical evidence exists.

---

## 20. Non-goals for the first version

The coding agent should avoid expanding the MVP into:

- a distributed microservice system;
- a general enterprise workflow platform;
- a marketplace of dozens of agent personas;
- autonomous financial execution;
- a polished multi-tenant billing system;
- arbitrary recursive agent spawning;
- indefinite debate loops;
- complex vector-memory infrastructure without a demonstrated need;
- a bespoke model gateway; or
- a domain-general ontology covering all possible decisions.

A local or single-user application with clear artifacts and reliable workflow control is sufficient.

---

## 21. Open questions to resolve through implementation

The following are intentionally left open and should be answered empirically:

1. How reliably can Cursor CLI be invoked concurrently without session or workspace interference?
2. Which Cursor-accessible models are best for each role?
3. How much included Cursor usage does a typical decision consume?
4. Does using different model families for Director and Challenger materially improve outcomes?
5. Which artifact formats produce the best balance between rigor and context size?
6. How much user clarification is necessary before investigation begins?
7. What is the best stopping rule in practice?
8. Should the final citation verifier independently reopen sources or only inspect stored evidence?
9. When does a general Researcher suffice, and when is a domain specialist necessary?
10. Which probability-estimation techniques are useful before historical calibration data exists?
11. How should the system represent genuine disagreement that cannot be resolved?
12. Which parts of the workflow benefit from a visual interface versus plain Markdown artifacts?

These are experimental questions, not reasons to delay the MVP.

---

## 22. Product decision log

### Use multiple agents, but only for distinct functions

**Decision:** Adopt specialized control and worker roles rather than one monolithic agent or an unrestricted agent society.

**Rationale:** Specialization and context isolation may reduce context degradation and correlated mistakes, but excessive roles create duplication and cost.

### Use Director–Challenger review rather than model voting

**Decision:** A Director forms the thesis and a different-model Challenger attempts to falsify it.

**Rationale:** Majority agreement does not constitute a calibrated probability. Structured adversarial review is more useful than counting votes.

### Keep planning separate from substantive decision ownership

**Decision:** The Planner owns the work plan; the Director owns the decision thesis.

**Rationale:** This prevents the investigation process from silently redefining the decision to match available research.

### Use an Auditor as process control

**Decision:** The Steerer becomes a constrained Process Auditor rather than another broad reasoning participant.

**Rationale:** Its purpose is to maintain relevance, quality, and stopping discipline—not add another opinion.

### Use temporary workers

**Decision:** Researchers, Analysts, and Specialists are spawned for narrow assignments and do not retain broad persistent context.

**Rationale:** This reduces context contamination, duplicated work, and unnecessary token consumption.

### Use structured blackboard artifacts

**Decision:** Agents exchange normalized evidence, assumptions, tasks, objections, and analyses rather than full conversation histories.

**Rationale:** Traceability and context hygiene are core product requirements.

### Use Cursor CLI for the personal MVP

**Decision:** Use the existing Cursor subscription and Cursor CLI as the first agent execution harness.

**Rationale:** It already supplies multi-model access and coding-agent tools, has low marginal cost for the user, and keeps the initial stack simple.

### Do not couple the platform permanently to Cursor

**Decision:** Define a backend-neutral agent execution boundary.

**Rationale:** Direct provider APIs or OpenRouter may later offer better model control, observability, concurrency, or cost management.

### Use a thin deterministic orchestrator above the harness

**Decision:** Workflow control is ordinary application code. No agent, including the Planner, mechanically launches other agents.

**Rationale:** Routing, budgets, validation, stopping rules, and approval gates must not depend on model behavior.

### Use a file-based blackboard first

**Decision:** Case state lives in structured files inside a case directory. A database is introduced only when file semantics become limiting.

**Rationale:** Files are inspectable, diffable, and native to a coding-agent harness, and the conceptual model survives a later storage migration.

### Defer workflow frameworks

**Decision:** No LangGraph or similar orchestration framework in the MVP.

**Rationale:** The first workflow is well defined enough for a small custom state machine. Frameworks earn their place when durability, branching complexity, or distributed execution demand them.

### Plan a phased backend roadmap

**Decision:** Phase 1 runs every role through Cursor CLI. Phase 2 may move strict structured-output roles to direct APIs behind the same backend boundary. Phase 3, production hardening, is out of scope.

**Rationale:** The Analyst gains the most from a coding harness; the Director, Challenger, and Synthesizer eventually gain more from direct model control and reproducible prompts.

### Do not optimize for production SaaS concerns yet

**Decision:** Build for a single user and local/personal execution first.

**Rationale:** The main risk is product validity, not infrastructure scalability.

---

## 23. Direction to the coding agent

Build the smallest system that faithfully demonstrates the decision process described here.

Prioritize:

- a transparent state machine;
- clear role definitions;
- isolated contexts;
- robust structured artifacts;
- reproducible quantitative analysis;
- source provenance;
- a strong Director–Challenger cycle;
- sensible stopping rules; and
- a useful final recommendation.

Avoid solving hypothetical scaling problems before the platform has produced several genuinely useful personal decisions.

When uncertain, choose the design that makes it easier to answer:

> What did the system believe, what evidence supported it, what assumptions did it make, what challenged it, and why did it ultimately recommend this action?

---

## 24. Current reference sources

The implementation agent should re-check current documentation before relying on specific CLI flags, supported models, quotas, or pricing because these can change.

- Cursor, **Using Headless CLI**: <https://cursor.com/docs/cli/headless>
- Cursor, **Cursor CLI overview**: <https://cursor.com/docs/cli/overview>
- Cursor, **Using Agent in CLI**: <https://cursor.com/docs/cli/using>
- Cursor, **Documentation overview**: <https://cursor.com/docs>
- Cursor, **Pricing**: <https://cursor.com/pricing>
- Cursor, **Increased usage for agents** (2026-02-11): <https://cursor.com/blog/increased-agent-usage>
- OpenRouter, **Quickstart**: <https://openrouter.ai/docs/quickstart>
- OpenRouter, **Pricing**: <https://openrouter.ai/pricing>
- OpenRouter, **Pricing and fees FAQ**: <https://openrouter.ai/docs/faq>
- OpenRouter, **Bring Your Own Keys**: <https://openrouter.ai/docs/guides/overview/auth/byok>

