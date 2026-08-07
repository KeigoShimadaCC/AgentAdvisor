import { stageLabel } from "../../copy/terms";
import type { CaseView } from "../../generated/case_view";

interface CaseMapProps {
  view: CaseView;
  /** Live loop counters, from the projection's effort/state counters. */
  counters?: LoopCounters;
}

export interface LoopCounters {
  repairCycle: number;
  repairCap: number;
  synthesisRetries: number;
  synthesisCap: number;
  framingRevisions: number;
  framingCap: number;
  finalRevisions: number;
  finalCap: number;
}

/**
 * One phase of the engagement, and the stages that actually run inside it.
 *
 * The stage lists are the point. `MethodStrip` showed six phases and nothing
 * else, so a case could spend twenty minutes going around the challenge cycle
 * a second time and the indicator never moved — a second round was
 * pixel-identical to a stall.
 */
interface PhaseSpec {
  phase: string;
  label: string;
  stages: string[];
  /** The cycle this phase contains, if any. Every one is intra-phase. */
  cycle?: { label: string; from: string; to: string };
  /** Stages that wait for a human signature. */
  gates?: string[];
}

const PHASES: PhaseSpec[] = [
  { phase: "intake", label: "Intake", stages: ["intake"] },
  {
    phase: "framing",
    label: "Framing",
    stages: ["framing", "awaiting_framing_approval"],
    cycle: { label: "rescope", from: "awaiting_framing_approval", to: "framing" },
    gates: ["awaiting_framing_approval"],
  },
  {
    phase: "investigation",
    label: "Investigation",
    stages: [
      "structuring",
      "provisional_thesis",
      "planning",
      "investigation",
      "evidence_critique",
      "assumption_ledger",
      "competing_hypotheses",
      "preliminary_recommendation",
    ],
  },
  {
    phase: "challenge",
    label: "Challenge",
    stages: ["pre_mortem", "challenge", "stop_decision", "repair"],
    cycle: { label: "repair", from: "repair", to: "challenge" },
  },
  {
    phase: "synthesis",
    label: "Synthesis",
    stages: ["synthesis", "review", "awaiting_final_approval"],
    cycle: { label: "re-review", from: "review", to: "synthesis" },
    gates: ["awaiting_final_approval"],
  },
  { phase: "complete", label: "Complete", stages: ["done"] },
];

/** Which cycle counter belongs to which phase, and its cap. */
function cycleCount(phase: string, counters: LoopCounters | undefined) {
  if (!counters) return null;
  switch (phase) {
    case "framing":
      return { used: counters.framingRevisions, cap: counters.framingCap };
    case "challenge":
      return { used: counters.repairCycle, cap: counters.repairCap };
    case "synthesis":
      return { used: counters.synthesisRetries, cap: counters.synthesisCap };
    default:
      return null;
  }
}

/**
 * The case map (SPEC-047) — replaces `MethodStrip`.
 *
 * Two things it does that a linear strip structurally cannot:
 *
 *  1. **Draws the cycles permanently**, so a loop is a visible part of the plan
 *     before it ever runs rather than a surprise when it does.
 *  2. **Counts the rounds.** "Challenge — round 2 of 2" is the only thing that
 *     distinguishes productive re-work from a hang, and every counter it needs
 *     was already in `CaseState`, visible until now only as a raw meter buried
 *     in the Method room.
 */
export function CaseMap({ view, counters }: CaseMapProps) {
  const currentIndex = PHASES.findIndex((p) => p.phase === view.phase);

  return (
    // The map scrolls horizontally on narrow viewports, and a scrollable
    // region has to be reachable by keyboard — the same defect SPEC-045 fixed
    // in the Method room's audit log, reintroduced here by a new component.
    // Worth stating: the axe sweep caught it within minutes of it existing.
    <section className="case-map" aria-label="Where this case is" tabIndex={0}>
      <ol className="case-map-phases">
        {PHASES.map((spec, i) => {
          const state =
            currentIndex === -1
              ? "pending"
              : i < currentIndex
                ? "done"
                : i === currentIndex
                  ? "current"
                  : "pending";
          const cycle = cycleCount(spec.phase, counters);
          const inCycle = cycle !== null && cycle.used > 0;

          return (
            <li
              key={spec.phase}
              className={`case-map-phase case-map-phase-${state}${inCycle ? " case-map-phase-looping" : ""}`}
              aria-current={state === "current" ? "step" : undefined}
              data-phase={spec.phase}
            >
              <span className="case-map-phase-label">{spec.label}</span>

              <ul className="case-map-stages">
                {spec.stages.map((stage) => (
                  <li
                    key={stage}
                    className={`case-map-stage${stage === view.stage ? " case-map-stage-current" : ""}`}
                    data-stage={stage}
                  >
                    {stageLabel(stage)}
                    {spec.gates?.includes(stage) && (
                      <span className="case-map-gate" title="Waits for your signature">
                        {" "}
                        — needs you
                      </span>
                    )}
                  </li>
                ))}
              </ul>

              {spec.cycle && (
                <p
                  className={`case-map-cycle${inCycle ? " case-map-cycle-active" : ""}`}
                  data-cycle={spec.cycle.label}
                >
                  <span aria-hidden="true">↻ </span>
                  {cycle && cycle.used > 0 ? (
                    <span data-testid={`cycle-${spec.cycle.label}`}>
                      {spec.cycle.label} — round {cycle.used + 1} of {cycle.cap + 1}
                    </span>
                  ) : (
                    <span data-testid={`cycle-${spec.cycle.label}`}>
                      can {spec.cycle.label}
                      {cycle ? ` up to ${cycle.cap}×` : ""}
                    </span>
                  )}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** Pull the loop counters out of a projection, with the caps the engine uses. */
export function countersFromView(view: CaseView): LoopCounters {
  const budget = (view.effort?.budget_counters ?? {}) as Record<string, number>;
  const caps = (view.effort?.budget_caps ?? {}) as Record<string, number>;
  return {
    repairCycle: budget.repair_cycles ?? 0,
    repairCap: caps.max_repair_cycles ?? 2,
    synthesisRetries: budget.synthesis_retries ?? 0,
    synthesisCap: 1,
    framingRevisions: budget.framing_revisions ?? 0,
    framingCap: 2,
    finalRevisions: budget.final_revisions ?? 0,
    finalCap: 1,
  };
}
