# AGENTS.md — Decision Intelligence Platform

Operating guide for coding agents working in this repository.

## What this project is

A personal multi-agent decision-intelligence platform. Given an imperfectly defined decision ("Should I invest in AAA?"), it runs a structured process (framing, alternatives, evidence, assumptions, quantitative scenarios, adversarial challenge, synthesis) and returns a recommendation with explicit uncertainty and an inspectable chain from objectives to conclusion.

It behaves like a small consulting team or investment committee, not a search assistant and not a multi-agent chat room.

## Read first

- `decision_intelligence_north_star.md` is the authoritative product and architecture direction. Read it before writing code.
- `PROJECT_PLAN.md` (root) is the static plan: goal, definition of done, phase structure and dependencies. Do not update it with progress; live status belongs in `specs/ROADMAP.md`.
- If this file and the north star conflict: the north star wins on product intent and architecture; this file wins on repository mechanics.
- Re-check current Cursor CLI docs (north star Section 24) before relying on specific CLI flags, models, or quotas.

## Two harnesses, do not confuse them

- **Factory AI (this environment) develops the platform:** writes specs, orchestrator code, schemas, and tests. This file is its guidance.
- **Cursor CLI is the runtime harness for the product's own agents.** Everything under `cursor/` (role definition mds, skill mds) is a product artifact consumed by headless `cursor-agent` invocations at case runtime, not guidance for the development agent.

## Repository layout

```
specs/         # spec sheets grouped by phase; process in specs/README.md, status in specs/ROADMAP.md
schemas/       # versioned artifact schemas (JSON Schema or equivalent)
orchestrator/  # deterministic Python orchestrator
cursor/
  roles/       # Cursor CLI agent definitions (director, planner, challenger, auditor, researcher, analyst, synthesizer, reviewer)
  skills/      # Cursor skill packages for dynamically spawned domain specialists
cases/         # runtime case blackboards, gitignored (cases/<case-id>/ per north star 7.3)
benchmarks/    # benchmark decision cases for evaluation (north star Section 19)
tests/         # unit tests for deterministic components
report-and-findings/  # research reports, test findings, experiment writeups (dated files)
```

Reports, research findings, and experiment writeups belong in `report-and-findings/`, named `YYYY-MM-DD-<topic>.md`.

## Spec-driven development

Work proceeds spec first: write the spec sheet → user approves → implement → verify against the spec's acceptance criteria → mark verified → next spec.

- Do not implement functionality that has no approved spec in `specs/`.
- Do not mark a spec `verified` without executing its verification plan and recording the results in the spec.
- `specs/README.md` defines the lifecycle and parallelism rules; `specs/TEMPLATE.md` is the required format; `specs/ROADMAP.md` is the live status board (phase/spec states, per-phase findings, emergent work) and must be kept in sync.
- Newly discovered work goes to ROADMAP's "Emergent work" section first, then is promoted to a spec or phase with user approval. `PROJECT_PLAN.md` stays frozen.
- If implementation reveals the spec is wrong, update the spec first, then continue coding.

## Priorities when tradeoffs conflict (ordered)

1. Decision quality
2. Traceability from evidence to recommendation
3. Disciplined handling of uncertainty
4. Context isolation between agents
5. Simplicity appropriate for a personal project
6. Ability to change model providers later

## Hard architecture rules

- **Deterministic control.** Workflow state, routing, task status, iteration caps, budgets, schema validation, retries, stopping rules, and user approval gates live in ordinary code (the orchestrator). Never delegate these to a model. No agent, including the Planner, launches other agents.
- **Backend boundary.** All model execution goes through the `AgentBackend` interface. Cursor CLI is the first backend. Core decision logic must never depend on Cursor-specific or undocumented harness behavior.
- **Typed artifacts, not transcripts.** Agents communicate through schema-validated artifacts on the case blackboard (`cases/<case-id>/`). Never pass one agent's transcript into another agent's context. The orchestrator projects a minimal context per invocation.
- **Validate before accepting.** Every agent output is validated against its output schema before entering shared state. Invalid output is rejected and retried per the escalation ladder, not silently patched.
- **Reproducible quantitative work.** Numbers come from executed code saved under the case's `analysis/` directory, never from prose arithmetic.
- **Provenance is mandatory.** Evidence records keep source, dates, excerpt, limitations, and `independence_group`. Repeated coverage of one origin is one source.
- **Uncertainty measures stay distinct.** Outcome probability, evidence confidence, recommendation confidence, and model stability are different quantities. Never derive a probability from agent voting or collapse these into one number.
- **Workspace isolation.** Each agent invocation gets its own working directory. Concurrent invocations never share mutable files; shared state changes only through the orchestrator's normalization step.

## Scope discipline

- Single user, local execution. First vertical: investment-style decisions on a general substrate.
- Repair cycles are capped (one or two). Per-case budgets (north star Section 13) are enforced in code.
- Do not build, without explicit user direction: microservices, vector memory, agent-persona marketplaces, autonomous execution of consequential actions, recursive agent spawning, open-ended debate loops, a bespoke model gateway, or multi-tenant/billing features (Section 20).
- The system recommends; it does not execute financial transactions, send external communications, or take other consequential external actions without user approval (Section 14).

## Implementation conventions

- Orchestrator and analysis code in Python; prefer small, legible modules over frameworks. No LangGraph or similar until a demonstrated need. Confirm with the user before adding a major dependency or another language.
- Artifact schemas are versioned in code (JSON Schema or equivalent). Artifacts are YAML/JSON files with stable IDs: `E-` evidence, `A-` assumptions, `T-` tasks, `O-` objections.
- Cursor CLI invocations are headless subprocess calls: read inputs from files in the assigned working directory, write the validated artifact back. Verify flags against the installed CLI version.
- Log significant workflow events to the case audit log with enough usage metadata to compare decision quality against resource consumption.
- Never store secrets, API keys, or personal credentials in case artifacts, prompts, or logs.

## Testing and validation

- Unit-test the deterministic parts: routing, budget enforcement, schema validation, evidence normalization and deduplication, stopping rules.
- Maintain benchmark decision cases and compare the workflow against a single strong-agent baseline (Section 19).
- A completed case must be auditable from its artifacts alone: what the system believed, what evidence supported it, what assumptions it made, what challenged it, and why it recommended the action.
- Run whatever lint, typecheck, and test commands the project defines before considering a change complete.

## When uncertain

- Section 21 of the north star lists open empirical questions (CLI concurrency, model-per-role fit, usage per decision, stopping rules, and more). Prefer a small experiment over speculative abstraction.
- When implementation choices conflict, pick the design that best preserves the ordered priorities above and keeps the evidence-to-recommendation chain inspectable.
