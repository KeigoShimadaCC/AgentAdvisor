---
id: SPEC-015
title: Challenger role
phase: 3
status: draft
depends_on: [SPEC-006]
parallel_with: [SPEC-010, SPEC-011, SPEC-012, SPEC-013, SPEC-014, SPEC-016, SPEC-017]
north_star_refs: ["6.3", "8", "12"]
last_updated: 2026-07-30
---

# SPEC-015 — Challenger role

## Summary

Adversarial review from a different model family: a bounded set of material objections against the preliminary recommendation, each stating what evidence would reverse the conclusion.

## Motivation

North star 6.3 and the Director–Challenger decision-log entry: structured falsification instead of model voting; Section 12 requires family diversity precisely at this boundary.

## Scope

- `cursor/roles/challenger.md`: attack the preliminary recommendation via the 6.3 checklist (hidden assumptions, contrary evidence, omitted alternatives, bias tests, tail risks, load-bearing assumptions, reversal evidence); emit ≤5 `ObjectionRecord`s ranked by materiality, each with reasoning, referenced evidence/assumption IDs where applicable, and a `reversal_evidence` statement; manufactured disagreement explicitly prohibited: returning fewer, stronger objections is compliant, zero objections requires a stated justification.
- Family-diversity guard in `orchestrator/roles_config.py`: loading a config where `family(director.model) == family(challenger.model)` is a startup error.
- Final falsification pass (Stage 5.3 step 5) uses the same role md with `mode: final_pass` and a cap of 2 objections.
- `roles.yaml` entry: gpt-5.6-sol family per research report; projection: decision spec, preliminary recommendation, high-materiality assumptions, evidence summaries (bounded), prior resolved objections.
- Fixture: mini-blackboard with a deliberately over-confident recommendation containing a plantable flaw (uncited leap + fragile assumption).

## Out of scope

Objection triage and repair commissioning (Auditor SPEC-016, Planner SPEC-011, wiring SPEC-018).

## Design

Objection cap enforced by validation, not trust: >5 objections fails validation into the retry ladder. Each objection must name its target artifact section, making downstream repair targeting mechanical.

## Deliverables

- [ ] `cursor/roles/challenger.md`
- [ ] Family-diversity guard + `family()` mapping table
- [ ] `roles.yaml` entry, projection config
- [ ] `tests/test_role_challenger.py` + fixture; live mini-run test

## Acceptance criteria

- [ ] Config with same-family Director and Challenger fails to load with a clear error.
- [ ] Fixture replay: ≤5 schema-valid objections, each with materiality, target section, and reversal_evidence; >5 rejected by validation.
- [ ] Live mini-run against the flawed fixture recommendation surfaces the planted flaw in ≥1 objection (structural check: objection targets the planted section) in ≤2 attempts.
- [ ] `make check` green.

## Verification plan

```
make check
uv run pytest tests/test_role_challenger.py -q
uv run pytest -m live -k challenger -q
```

## Verification results

—

## Open questions

- Whether the live planted-flaw assertion is too flaky across models; if so, downgrade to manual inspection with the structural checks kept. Decide after first live run.
