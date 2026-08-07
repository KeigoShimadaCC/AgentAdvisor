# Final recommendation

## Executive recommendation
- [recommendation] Recommended action: invest_in_stages.
- [recommendation] Timing: Start with a small tranche this quarter and gate follow-on on milestone checks.

## Decision confidence
- [interpretation] Evidence favors staged entry, but downside concentration and one open objection remain material.
- [calculation] Recommendation confidence: 74.0% (basis: Staged entry dominates alternatives across most tested sensitivities.)
- [calculation] Evidence confidence: 63.0% (basis: One high-directness filing plus one medium-confidence comparative study with stated limits.)
- [calculation] Model stability: 80.0% (16/20 sensitivity runs support the recommendation).
- [calculation] Outcome probability — positive_return_within_5y: 59.0% via `structured_subjective`. [E-102]
- [calculation] Outcome probability — total_loss: 20.0% via `scenario_model`. [E-101]

## Alternatives considered
- [interpretation] Rank 1: `invest_in_stages` — Best downside-adjusted expected utility while retaining upside participation.
- [interpretation] Rank 2: `wait_for_milestone` — Lowers downside further but gives up current entry option value.
- [interpretation] Rank 3: `invest_now` — Highest upside capture but weakest downside protection under current uncertainty.

## Key reasons
- [interpretation] Downside concentration evidence remains material even after challenge-and-repair.
- [interpretation] Staged entry preserves option value while unresolved uncertainty is monitored.

## Scenario analysis
- [calculation] `upside`: Retention durability holds and growth remains above plan. (probability: 54.0%). [E-102]
- [calculation] `downside`: Competitive pricing pressure compresses margins and slows growth. (probability: 27.0%). [E-101]

## Quantitative findings
- [calculation] Expected utility favors staged entry by 8.5 points over invest_now in the base weighting.
- [calculation] Recommendation remains unchanged in 16 of 20 sensitivity runs.

## Strongest counterarguments
- [interpretation] Counterargument (unresolved): Competitor discounting could invalidate near-term margin assumptions.
  - [interpretation] Resolution/status detail: Partially resolved by lowering initial tranche size; still tracked as unresolved risk.

## Critical assumptions
- [assumption] A-001

## What would change the recommendation
- [interpretation] If retention drops below 110% for two consecutive quarters, switch to wait_for_milestone.
- [interpretation] If independent benchmark data contradicts filing-based retention durability, pause follow-on.

## Limitations
- [interpretation] No limitations were stated. Treat that as an omission rather than as a claim of completeness.

## Next actions

| # | Action | Owner | By | First step |
|---|---|---|---|---|
| N-001 | Define tranche sizing and downside guardrails before execution | user | 2026-08-15 | Block 30 minutes and start: define tranche sizing and downside guardrails before execution |
| N-002 | Collect one independent retention benchmark before second tranche release | user | 2026-08-22 | Block 30 minutes and start: collect one independent retention benchmark before second tranche release |

- [recommendation] N-001: Carries the recommendation into execution.
- [recommendation] N-002: Carries the recommendation into execution.

## User-supplied inputs
- [user_input] User requires downside protection over maximum upside.
- [user_input] User deadline for initial action is this quarter.

## Budget/depth stop disclosure
- [interpretation] Why it stopped: the investigation budget ran out; further research looked unlikely to change the answer.
- [interpretation] What ran out: max research tasks, wall clock.

## Evidence and citations
- [sourced_fact] Inline evidence references: [E-101] [E-102]

| Evidence ID | Claim | Publisher | Source URL | Publication date | Independence group |
| --- | --- | --- | --- | --- | --- |
| E-101 | Comparable investments show downside concentration when entry pricing is aggressive. | Example Capital Research | https://example.com/venture-outcome-review | 2026-03-01 | venture-outcomes-2026 |
| E-102 | AAA filed customer retention metrics above peer median in Q2. | AAA Investor Relations | https://example.com/aaa-q2-filing | 2026-06-20 | aaa-q2-filing |

## Provenance labels
- `[sourced_fact]`: sourced fact grounded in evidence records.
- `[assumption]`: explicit assumption references.
- `[calculation]`: quantitative or modeled statement.
- `[user_input]`: user-provided input.
- `[interpretation]`: synthesis interpretation.
- `[recommendation]`: normative recommendation statement.
