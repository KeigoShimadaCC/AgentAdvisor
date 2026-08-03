import type { CaseView } from "../../generated/case_view";
import type { TranslatedEvent } from "../../api/sse";

/**
 * Fixture CaseView projections and SSE events for the SPEC-036 room tests.
 *
 * These mirror the shapes produced by the orchestrator's build_case_view so
 * the rooms can be tested over realistic data without a running backend.
 */

export function makeSourcesFixture(): CaseView {
  return {
    case_id: "case-1",
    phase: "investigation",
    stage: "evidence_critique",
    is_terminal: false,
    needs_you: "none",
    rooms: {
      sources: {
        corpus_authority_mean: 0.62,
        independent_group_count: 4,
        max_cluster_share: 0.55,
        primary_source_share: 0.4,
        sources: [
          {
            evidence_id: "E-1",
            claim: "Revenue grew 12% YoY in Q2.",
            publisher: "SEC filing",
            source_url: "https://example.com/filing",
            source_type: "regulatory_filing",
            publication_date: "2025-04-01",
            independence_group: "grp-a",
            reliability: "high",
            directness: "high",
            source_tier: "primary",
            authority_score: 0.95,
            flags: [],
            cluster_share: 0.55,
          },
          {
            evidence_id: "E-2",
            claim: "Analyst note predicts margin pressure.",
            publisher: "Sell-side note",
            source_url: "https://example.com/note",
            source_type: "specialist_reporting",
            publication_date: "2025-03-15",
            independence_group: "grp-a",
            reliability: "medium",
            directness: "medium",
            source_tier: "reputable",
            authority_score: 0.45,
            flags: ["incentive_conflict"],
            cluster_share: 0.55,
          },
          {
            evidence_id: "E-3",
            claim: "Industry survey shows demand softening.",
            publisher: "Trade body",
            source_url: "https://example.com/survey",
            source_type: "original_research",
            publication_date: "2025-02-20",
            independence_group: "grp-b",
            reliability: "medium",
            directness: "low",
            source_tier: "official",
            authority_score: 0.3,
            flags: ["low_directness"],
            cluster_share: 0.25,
          },
        ],
      },
      assumptions: { assumptions: [] },
      options: { options: [], ev_table: {} },
      challenges: { objections: [] },
      plan: null,
    },
  };
}

export function makeAssumptionsFixture(): CaseView {
  return {
    case_id: "case-1",
    phase: "investigation",
    stage: "assumption_ledger",
    is_terminal: false,
    needs_you: "none",
    rooms: {
      sources: { sources: [] },
      assumptions: {
        assumptions: [
          {
            assumption_id: "A-1",
            claim: "Interest rates stay flat over the next year.",
            type: "forecast",
            status: "unresolved",
            materiality: "high",
            confidence: "low",
            evidence_for: ["E-1"],
            evidence_against: ["E-3", "E-2"],
            estimate_point: 0.4,
          },
          {
            assumption_id: "A-2",
            claim: "The team can hire two engineers this quarter.",
            type: "operational",
            status: "supported",
            materiality: "medium",
            confidence: "medium",
            evidence_for: ["E-1"],
            evidence_against: [],
            estimate_point: 0.7,
          },
          {
            assumption_id: "A-3",
            claim: "Regulatory approval is automatic.",
            type: "regulatory",
            status: "unresolved",
            materiality: "low",
            confidence: "medium",
            evidence_for: [],
            evidence_against: [],
            estimate_point: null,
          },
        ],
      },
      options: { options: [], ev_table: {} },
      challenges: { objections: [] },
      plan: null,
    },
  };
}

export function makeOptionsFixture(): CaseView {
  return {
    case_id: "case-1",
    phase: "synthesis",
    stage: "preliminary_recommendation",
    is_terminal: false,
    needs_you: "none",
    rooms: {
      sources: { sources: [] },
      assumptions: { assumptions: [] },
      options: {
        options: [
          {
            alternative: "Buy the ETF",
            rank: 1,
            rationale: "Lowest risk for the desired exposure.",
            expected_value: 0.62,
          },
          {
            alternative: "Buy the single stock",
            rank: 2,
            rationale: "Higher upside but concentrated risk.",
            expected_value: 0.41,
          },
          {
            alternative: "Wait for earnings",
            rank: 2,
            rationale: "Equal rank: defers decision without reducing upside materially.",
            expected_value: 0.43,
          },
          {
            alternative: "Do nothing",
            rank: 99,
            rationale: "Eliminated: does not meet the semiconductor-exposure objective.",
            expected_value: null,
          },
        ],
        ev_table: { "Buy the ETF": 0.62, "Buy the single stock": 0.41, "Wait for earnings": 0.43 },
      },
      challenges: { objections: [] },
      plan: null,
    },
  };
}

export function makeChallengesFixture(): CaseView {
  return {
    case_id: "case-1",
    phase: "challenge",
    stage: "challenge",
    is_terminal: false,
    needs_you: "none",
    rooms: {
      sources: { sources: [] },
      assumptions: { assumptions: [] },
      options: { options: [], ev_table: {} },
      challenges: {
        objections: [
          {
            objection_id: "O-2",
            target_section: "executive_recommendation",
            claim: "The ETF ignores company-specific upside.",
            materiality: "medium",
            resolution_status: "resolved",
            reasoning: "Addressed by including the single-stock alternative.",
          },
          {
            objection_id: "O-1",
            target_section: "alternatives_considered",
            claim: "Cost estimates omit tax drag.",
            materiality: "high",
            resolution_status: "open",
            reasoning: "No evidence yet on after-tax returns.",
          },
        ],
        premortem: {
          horizon: "12 months",
          assumed_outcome: "We bought the single stock and it halved.",
          most_likely_failure_mode: "Concentration risk materializes.",
          failure_modes: [
            {
              failure_mode: "Single-stock drawdown",
              severity: "high",
              probability_point: 0.35,
              narrative: "A single bad quarter halves the position.",
              leading_indicators: ["earnings miss", "guidance cut"],
            },
          ],
        },
        track_divergence: {
          stage: "challenge",
          agreement: false,
          divergence_summary: "Track B prefers waiting for earnings.",
          reconciled_alternative: null,
          positions: [
            {
              track_id: "track-a",
              model: "gpt-5",
              model_family: "openai",
              preferred_alternative: "Buy the ETF",
              top_reason: "Diversification",
              recommendation_confidence: 0.7,
            },
            {
              track_id: "track-b",
              model: "claude-4",
              model_family: "anthropic",
              preferred_alternative: "Wait for earnings",
              top_reason: "Information advantage",
              recommendation_confidence: 0.6,
            },
          ],
        },
      },
      plan: null,
    },
  };
}

export function makeTrackBAbsentFixture(): CaseView {
  const base = makeChallengesFixture();
  base.rooms!.challenges!.track_divergence = null;
  return base;
}

export function makePlanFixture(): CaseView {
  return {
    case_id: "case-1",
    phase: "investigation",
    stage: "structuring",
    is_terminal: false,
    needs_you: "none",
    rooms: {
      sources: { sources: [] },
      assumptions: { assumptions: [] },
      options: { options: [], ev_table: {} },
      challenges: { objections: [] },
      plan: {
        decision_question: "Should I buy a single stock, an ETF, or wait?",
        coverage_fraction: 0.5,
        mece_justification: "Three mutually exclusive paths cover the decision space.",
        nodes: [
          {
            node_id: "Q-1",
            parent_id: null,
            question: "Should I buy a single stock, an ETF, or wait?",
            node_type: "root",
            materiality: "high",
            resolution_criteria: "A ranked recommendation.",
            covered: true,
          },
          {
            node_id: "Q-1.1",
            parent_id: "Q-1",
            question: "What is the risk-adjusted return of each option?",
            node_type: "driver",
            materiality: "high",
            resolution_criteria: "EV estimates per option.",
            covered: true,
          },
          {
            node_id: "Q-1.2",
            parent_id: "Q-1",
            question: "What are the tax implications?",
            node_type: "driver",
            materiality: "medium",
            resolution_criteria: "After-tax return estimate.",
            covered: false,
          },
        ],
      },
    },
  };
}

export function makeMethodFixture(): CaseView {
  return {
    case_id: "case-1",
    phase: "complete",
    stage: "done",
    is_terminal: true,
    needs_you: "none",
    effort: {
      invocation_attempts: 5,
      invocation_successes: 5,
      retries: 1,
      input_tokens: 12000,
      output_tokens: 8000,
      total_tokens: 20000,
      wall_clock_s: 642,
      budget_counters: { agent_invocations: 5 },
      budget_caps: { max_agent_invocations: 25 },
      by_role: {
        researcher: { attempts: 2, input_tokens: 5000, output_tokens: 3000, total_tokens: 8000 },
        analyst: { attempts: 3, input_tokens: 7000, output_tokens: 5000, total_tokens: 12000 },
      },
      event_counts: { role_invocation_attempt: 5, stage_completed: 6 },
    },
    integrity: {
      gates: [
        { stage: "evidence_critique", outcome: "pass", findings: [] },
        { stage: "assumption_ledger", outcome: "pass", findings: [{ check_id: "min-coverage", severity: "low", message: "Coverage at 50%.", target_ids: [] }] },
      ],
    },
  };
}

export function makeEventsFixture(): TranslatedEvent[] {
  return [
    {
      event_type: "stage_completed",
      message: "Completed stage: framing",
      technical: false,
      raw_payload: { stage: "framing" },
      line_cursor: 1,
      ts: "2025-01-01T00:00:00Z",
      actor: "director",
    },
    {
      event_type: "role_invocation_attempt",
      message: "researcher is running…",
      technical: true,
      raw_payload: { attempt: 1, status: "ok", evidence_ids: ["E-1"] },
      line_cursor: 2,
      ts: "2025-01-01T00:01:00Z",
      actor: "researcher",
    },
    {
      event_type: "evidence_batch_unpacked",
      message: "1 evidence record(s) gathered for task T-1",
      technical: false,
      raw_payload: { record_count: 1, task_id: "T-1", evidence_ids: ["E-1"] },
      line_cursor: 3,
      ts: "2025-01-01T00:02:00Z",
      actor: "researcher",
    },
  ];
}
