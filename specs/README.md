# Specs — spec-driven development process

All work on this project is spec-driven. No functionality is implemented without an approved spec, and no spec is closed without passing its verification plan.

## Lifecycle

Every spec moves through these states, in order:

1. `draft` — spec sheet written from `TEMPLATE.md`; open questions allowed.
2. `approved` — the user has reviewed and approved scope, design, and acceptance criteria.
3. `in_progress` — implementation underway.
4. `implemented` — all deliverables exist; verification not yet run or not yet passing.
5. `verified` — verification plan executed and passing; results recorded in the spec itself.

Only then does work move to the next spec. If verification fails, the spec returns to `in_progress` (implementation bug) or `draft` (the plan itself was wrong), and the state change is noted in the spec.

## Organization

- Specs live in per-phase folders: `specs/phase-<n>-<name>/`.
- Files are named `SPEC-<nnn>-<short-title>.md` with a globally unique, monotonically increasing number (e.g. `SPEC-003-artifact-schemas.md`).
- `ROADMAP.md` is the single status board: every spec, its phase, status, and dependencies.

## Sequencing and parallelism

- Phases are sequential by default; specs within a phase may run in parallel.
- Each spec declares `depends_on` (must be `verified` first) and `parallel_with` (safe to implement concurrently) in its front matter.
- Two specs may only be `parallel_with` each other if they touch disjoint files and neither consumes the other's deliverables. When in doubt, sequence them.

## Rules

- The spec is the contract. If implementation reveals the spec is wrong, update the spec first (and get re-approval if scope or acceptance criteria change), then continue coding.
- Acceptance criteria must be objectively checkable: a command to run, a file that must exist and validate, a test that must pass.
- Verification results are written into the spec's "Verification results" section with the date and the commands/evidence used.
- Keep specs small. A spec that cannot be implemented and verified in one focused session should be split.
- Product intent questions are settled by `../decision_intelligence_north_star.md`; specs must cite the sections they implement.
