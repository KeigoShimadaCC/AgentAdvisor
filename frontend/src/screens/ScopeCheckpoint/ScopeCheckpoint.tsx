import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { api, type ErrorResponse } from "../../api/client";
import type { CaseView } from "../../generated/case_view";
import type { IntakeRecord } from "../../generated/intake_record";
import type { DecisionSpec } from "../../generated/decision_spec";
import {
  SCOPE_COPY,
  EFFORT_PROFILES,
  OPTION_ORIGIN_LABELS,
  GROUND_RULE_KEYS,
  GROUND_RULE_LABELS,
  riskToleranceLabel,
  reversibilityLabel,
  RISK_TOLERANCE_OPTIONS,
  REVERSIBILITY_OPTIONS,
  EFFORT_LIMITS_INTRO,
  WHAT_IT_CAN_DO,
  WHAT_IT_CANT_DO,
  type OptionOrigin,
  type EffortKey,
} from "../../copy/terms";
import {
  type SheetState,
  buildApprovePayload,
  buildRevisionPayload,
  needsRevision,
  canonicalSheetContent,
  computeSummaryHash,
  allGroundRulesConfirmed,
  weightTotal,
  weightsAreValid,
  WEIGHT_BUDGET,
} from "./sheetPayload";

/**
 * SPEC-038. Seed the point allocation from the framing director's proposal,
 * rescaled to the {@link WEIGHT_BUDGET}.  Returns an empty allocation when the
 * framing proposed nothing, which means the case simply runs without a value
 * model — the same behaviour as before the weights existed.
 */
function seedWeights(spec: DecisionSpec): Record<string, number> {
  const proposed = spec.objective_weights;
  const objectives = spec.objectives ?? [];
  if (!proposed || Object.keys(proposed).length === 0 || objectives.length === 0) return {};

  const total = Object.values(proposed).reduce<number>((sum, n) => sum + Number(n), 0);
  if (total <= 0) return {};

  // Largest-remainder apportionment so the displayed points sum to exactly the
  // budget; naive rounding drifts off 100 and would block the sign gate.
  const exact = objectives.map((name) => (Number(proposed[name] ?? 0) / total) * WEIGHT_BUDGET);
  const floors = exact.map(Math.floor);
  let remaining = WEIGHT_BUDGET - floors.reduce((sum, n) => sum + n, 0);
  const order = exact
    .map((value, index) => ({ index, remainder: value - Math.floor(value) }))
    .sort((a, b) => b.remainder - a.remainder);
  for (const { index } of order) {
    if (remaining <= 0) break;
    floors[index] += 1;
    remaining -= 1;
  }
  return Object.fromEntries(
    objectives.map((name, index) => [name, floors[index]]).filter(([, points]) => (points as number) > 0),
  );
}

/** Map a backend effort/depth value to a UI EffortKey. */
function effortKeyFromDepth(depth: string | null | undefined): EffortKey {
  if (depth === "light") return "quick";
  if (depth === "deep") return "deep";
  return "standard";
}

/** Words too common to carry any signal about which option a phrase refers to. */
const OPTION_STOPWORDS = new Set([
  "a", "an", "and", "at", "be", "buy", "for", "from", "get", "go", "in", "into",
  "it", "keep", "my", "now", "of", "on", "or", "own", "stay", "than", "the",
  "then", "to", "up", "with",
]);

function optionTokens(value: string): Set<string> {
  return new Set(
    value
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter((t) => t.length > 2 && !OPTION_STOPWORDS.has(t)),
  );
}

/**
 * Decide whether the user proposed an option or the analysis added it.
 *
 * Exact string equality is wrong here: framing is *specified* to restate and
 * broaden what intake captured, so "Buy a condo" becoming "Buy a condo now"
 * would credit the system with the user's own option — a false provenance claim
 * on the sheet they sign. We compare significant tokens instead, and require a
 * clear majority overlap so a genuinely new alternative is still marked as ours.
 */
function optionOrigin(
  option: string,
  intakeOptions: string[] | null | undefined,
  userAdded: ReadonlySet<string>,
): OptionOrigin {
  // An option the user typed into "add a missing option" on this sheet is
  // theirs by construction — it never went through intake, so the token
  // comparison below would always mis-credit it to the analysis.
  if (userAdded.has(option)) return "yours";
  if (!intakeOptions || intakeOptions.length === 0) return "added-by-analysis";

  const optionTerms = optionTokens(option);
  if (optionTerms.size === 0) {
    return intakeOptions.some((o) => o.trim().toLowerCase() === option.trim().toLowerCase())
      ? "yours"
      : "added-by-analysis";
  }

  for (const candidate of intakeOptions) {
    const candidateTerms = optionTokens(candidate);
    if (candidateTerms.size === 0) continue;
    let shared = 0;
    for (const term of optionTerms) {
      if (candidateTerms.has(term)) shared += 1;
    }
    // Overlap is measured against the smaller phrase so that a restatement which
    // only adds words ("… now", "… instead") still resolves to the user's option.
    if (shared / Math.min(optionTerms.size, candidateTerms.size) >= 0.6) {
      return "yours";
    }
  }
  return "added-by-analysis";
}

export function ScopeCheckpoint() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [view, setView] = useState<CaseView | null>(null);
  const [intake, setIntake] = useState<IntakeRecord | null>(null);
  const [spec, setSpec] = useState<DecisionSpec | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // ── Editable sheet state ────────────────────────────────────────────────
  const [restatement, setRestatement] = useState("");
  const [options, setOptions] = useState<string[]>([]);
  // Keyed by option text rather than index so removing an option cannot
  // silently re-point a note at a different alternative.
  const [optionAnnotations, setOptionAnnotations] = useState<Record<string, string>>({});
  const [userAddedOptions, setUserAddedOptions] = useState<Set<string>>(new Set());
  const [newOption, setNewOption] = useState("");
  const [excludedQuestions, setExcludedQuestions] = useState<Set<string>>(new Set());
  const [confirmations, setConfirmations] = useState<Record<string, boolean>>({});
  // Ground-rule values the user overrode on this sheet (key → new value).
  const [groundRuleEdits, setGroundRuleEdits] = useState<Record<string, string>>({});
  const [revisionNotice, setRevisionNotice] = useState<string | null>(null);

  // Track the original restatement so we can detect edits.
  const [originalRestatement, setOriginalRestatement] = useState("");
  // SPEC-038: the elicited value model — points allocated across objectives.
  const [objectiveWeights, setObjectiveWeights] = useState<Record<string, number>>({});
  const [originalObjectiveWeights, setOriginalObjectiveWeights] = useState<Record<string, number>>({});

  async function loadAll() {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const [v, intakeEnv, specEnv] = await Promise.all([
        api.getCaseView(caseId),
        api.getIntakeRecord(caseId).catch(() => null),
        api.getDecisionSpec(caseId).catch(() => null),
      ]);
      setView(v);
      if (intakeEnv) setIntake(intakeEnv.data);
      if (specEnv) {
        setSpec(specEnv.data);
        const r = specEnv.data.question;
        setRestatement(r);
        setOriginalRestatement(r);
        setOptions(specEnv.data.alternatives ? [...specEnv.data.alternatives] : []);
        // Every piece of pending sheet input is relative to the spec we just
        // replaced, so all of it resets together.  Leaving any of it behind
        // makes ``needsRevision`` true forever and the sheet can never be
        // signed — the user would loop through revisions without being told
        // which stale edit is holding the gate shut.
        setExcludedQuestions(new Set());
        setOptionAnnotations({});
        setUserAddedOptions(new Set());
        setGroundRuleEdits({});
        setNewOption("");
        const seeded = seedWeights(specEnv.data);
        setObjectiveWeights(seeded);
        setOriginalObjectiveWeights(seeded);
        // Initialize confirmations as all-unconfirmed.
        const keys = [GROUND_RULE_KEYS.deadline, GROUND_RULE_KEYS.riskTolerance, GROUND_RULE_KEYS.reversibility];
        setConfirmations(Object.fromEntries(keys.map((k) => [k, false])));
      }
    } catch (e) {
      const err = e as ErrorResponse;
      setError(err.detail ?? err.error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId]);

  // ── Derived data ──────────────────────────────────────────────────────────
  const intakeOptions = intake?.alternatives_mentioned ?? null;
  const outlineQuestions: string[] = useMemo(() => {
    if (!spec) return [];
    // The investigation outline is the framing spec's objectives.
    return spec.objectives ? [...spec.objectives] : [];
  }, [spec]);

  const effortKey: EffortKey = effortKeyFromDepth(spec?.depth);
  const effortProfile = EFFORT_PROFILES[effortKey];

  const groundRuleKeys = [GROUND_RULE_KEYS.deadline, GROUND_RULE_KEYS.riskTolerance, GROUND_RULE_KEYS.reversibility];

  // Raw (enum/date) ground-rule values, with any user override applied.
  const groundRuleRawValues: Record<string, string> = {
    [GROUND_RULE_KEYS.deadline]: groundRuleEdits[GROUND_RULE_KEYS.deadline] ?? spec?.deadline ?? "",
    [GROUND_RULE_KEYS.riskTolerance]:
      groundRuleEdits[GROUND_RULE_KEYS.riskTolerance] ?? spec?.risk_tolerance ?? "",
    [GROUND_RULE_KEYS.reversibility]:
      groundRuleEdits[GROUND_RULE_KEYS.reversibility] ?? spec?.reversibility ?? "",
  };

  // The same values rendered through the lexicon for display.
  const groundRuleValues: Record<string, string> = {
    [GROUND_RULE_KEYS.deadline]: groundRuleRawValues[GROUND_RULE_KEYS.deadline],
    [GROUND_RULE_KEYS.riskTolerance]: riskToleranceLabel(groundRuleRawValues[GROUND_RULE_KEYS.riskTolerance]),
    [GROUND_RULE_KEYS.reversibility]: reversibilityLabel(groundRuleRawValues[GROUND_RULE_KEYS.reversibility]),
  };
  const assumedBecauseSkipped: Record<string, boolean> = {
    [GROUND_RULE_KEYS.deadline]: !intake?.deadline,
    [GROUND_RULE_KEYS.riskTolerance]: !intake?.risk_tolerance,
    [GROUND_RULE_KEYS.reversibility]: !intake?.reversibility,
  };

  // ── Sheet state for payload assembly ─────────────────────────────────────
  const sheetState: SheetState = {
    restatement,
    options,
    originalOptions: spec?.alternatives ? [...spec.alternatives] : [],
    excludedQuestions: [...excludedQuestions],
    optionAnnotations,
    groundRuleEdits,
    confirmations,
    groundRuleKeys,
    clarificationAnswers: {},
    objectiveWeights,
    originalObjectiveWeights,
  };

  const revisionNeeded = needsRevision(sheetState, originalRestatement);
  const weightsValid = weightsAreValid(objectiveWeights);
  const canSign = allGroundRulesConfirmed(sheetState) && weightsValid && !submitting;

  // ── Mutations ─────────────────────────────────────────────────────────────
  function removeOption(index: number) {
    const removed = options[index];
    setOptions((prev) => prev.filter((_, i) => i !== index));
    setOptionAnnotations((prev) => {
      const { [removed]: _dropped, ...rest } = prev;
      return rest;
    });
    setUserAddedOptions((prev) => {
      if (!prev.has(removed)) return prev;
      const next = new Set(prev);
      next.delete(removed);
      return next;
    });
  }

  function annotateOption(option: string, text: string) {
    setOptionAnnotations((prev) => ({ ...prev, [option]: text }));
  }

  function addOption() {
    const text = newOption.trim();
    if (!text) return;
    if (options.includes(text)) {
      setNewOption("");
      return;
    }
    setOptions((prev) => [...prev, text]);
    setUserAddedOptions((prev) => new Set(prev).add(text));
    setNewOption("");
  }

  function editGroundRule(key: string, value: string) {
    setGroundRuleEdits((prev) => ({ ...prev, [key]: value }));
    // A changed constraint invalidates the confirmation the user gave for the
    // value they saw before, so they must re-confirm the new one.
    setConfirmations((prev) => ({ ...prev, [key]: false }));
  }

  function toggleQuestion(q: string) {
    setExcludedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(q)) next.delete(q);
      else next.add(q);
      return next;
    });
  }

  function setObjectiveWeight(objective: string, points: number) {
    setObjectiveWeights((prev) => ({ ...prev, [objective]: points }));
  }

  function toggleConfirmation(key: string) {
    setConfirmations((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  // ── Submit handlers ───────────────────────────────────────────────────────
  async function handleSign() {
    if (!caseId || !canSign) return;
    setSubmitting(true);
    setError(null);
    try {
      if (revisionNeeded) {
        // Route through the framing-revision path, then re-present the sheet.
        const payload = buildRevisionPayload(sheetState);
        await api.submitScopeCheckpoint(caseId, payload);
        setRevisionNotice(
          "Revised framing requested. The sheet will re-present with the updated spec.",
        );
        // Re-load after the revision settles.
        await loadAll();
      } else {
        // Clean sign.
        const content = canonicalSheetContent(sheetState);
        const summaryHash = computeSummaryHash(content);
        const payload = buildApprovePayload(sheetState, summaryHash);
        await api.submitScopeCheckpoint(caseId, payload);
        // Transition to the signed record view.
        navigate(`/cases/${caseId}/scope/signed`);
      }
    } catch (e) {
      const err = e as ErrorResponse;
      setError(err.detail ?? err.error);
    } finally {
      setSubmitting(false);
    }
  }

  function handleSaveLater() {
    navigate(`/cases/${caseId}`);
  }

  // ── Render gates ──────────────────────────────────────────────────────────
  if (loading) return <p>Loading…</p>;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!spec) return <p className="error">The framing is not ready yet. Refresh in a moment.</p>;

  return (
    <div className="scope-checkpoint">
      {revisionNotice && (
        <p className="revision-notice" role="status">{revisionNotice}</p>
      )}

      {/* ── Decision restatement ─────────────────────────────────────────── */}
      <section className="scope-section">
        <h2>{SCOPE_COPY.restatementTitle}</h2>
        <p className="section-help">{SCOPE_COPY.restatementHelp}</p>
        <label htmlFor="restatement" className="sr-only">Decision restatement</label>
        <textarea
          id="restatement"
          className="restatement-input"
          value={restatement}
          onChange={(e) => setRestatement(e.target.value)}
          rows={4}
        />
      </section>

      {/* ── Options ───────────────────────────────────────────────────────── */}
      <section className="scope-section">
        <h2>{SCOPE_COPY.optionsTitle}</h2>
        <p className="section-help">{SCOPE_COPY.optionsHelp}</p>
        <ul className="options-list">
          {options.map((opt, i) => {
            const origin = optionOrigin(opt, intakeOptions, userAddedOptions);
            const annotationId = `option-note-${i}`;
            return (
              <li key={`${opt}-${i}`} className="option-row">
                <div className="option-row-main">
                  <span className={`option-origin origin-${origin}`} aria-label={OPTION_ORIGIN_LABELS[origin]}>
                    {OPTION_ORIGIN_LABELS[origin]}
                  </span>
                  <span className="option-text">{opt}</span>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => removeOption(i)}
                    aria-label={`Remove option: ${opt}`}
                  >
                    Remove
                  </button>
                </div>
                <label htmlFor={annotationId} className="sr-only">
                  {`${SCOPE_COPY.annotateLabel}: ${opt}`}
                </label>
                <input
                  id={annotationId}
                  type="text"
                  className="option-annotation-input"
                  placeholder={SCOPE_COPY.annotatePlaceholder}
                  value={optionAnnotations[opt] ?? ""}
                  onChange={(e) => annotateOption(opt, e.target.value)}
                />
              </li>
            );
          })}
        </ul>
        <div className="add-option">
          <label htmlFor="new-option" className="sr-only">Add an option</label>
          <input
            id="new-option"
            type="text"
            className="add-option-input"
            placeholder="Add a missing option"
            value={newOption}
            onChange={(e) => setNewOption(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addOption();
              }
            }}
          />
          <button type="button" className="secondary-action" onClick={addOption} disabled={!newOption.trim()}>
            Add option
          </button>
        </div>
      </section>

      {/* ── Investigation outline ─────────────────────────────────────────── */}
      <section className="scope-section">
        <h2>{SCOPE_COPY.outlineTitle}</h2>
        <p className="section-help">{SCOPE_COPY.outlineHelp}</p>
        <p className="outline-fidelity-note">{SCOPE_COPY.outlineFidelityNote}</p>
        <ul className="outline-list">
          {outlineQuestions.map((q) => {
            const struck = excludedQuestions.has(q);
            return (
              <li key={q} className={`outline-item${struck ? " struck" : ""}`}>
                <label>
                  <input
                    type="checkbox"
                    checked={struck}
                    onChange={() => toggleQuestion(q)}
                  />
                  <span className={struck ? "strike" : ""}>{q}</span>
                </label>
              </li>
            );
          })}
        </ul>
      </section>

      {/* ── Objective weights (SPEC-038) ──────────────────────────────────── */}
      {Object.keys(objectiveWeights).length > 0 && (
        <section className="scope-section">
          <h2>{SCOPE_COPY.weightsTitle}</h2>
          <p className="section-help">{SCOPE_COPY.weightsHelp}</p>
          <ul className="weight-list">
            {Object.keys(objectiveWeights).map((objective) => {
              const fieldId = `objective-weight-${objective.replace(/\s+/g, "-")}`;
              return (
                <li key={objective} className="weight-item">
                  <label htmlFor={fieldId} className="weight-label">{objective}</label>
                  <input
                    id={fieldId}
                    type="number"
                    className="weight-input"
                    min={0}
                    max={WEIGHT_BUDGET}
                    value={objectiveWeights[objective]}
                    onChange={(e) => setObjectiveWeight(objective, Number(e.target.value))}
                  />
                  <span className="weight-unit">points</span>
                </li>
              );
            })}
          </ul>
          <p className={`weight-total${weightsValid ? "" : " invalid"}`} role="status">
            {weightTotal(objectiveWeights)} / {WEIGHT_BUDGET} points allocated
            {weightsValid ? "" : ` — ${SCOPE_COPY.weightsInvalid}`}
          </p>
        </section>
      )}

      {/* ── Ground rules ──────────────────────────────────────────────────── */}
      <section className="scope-section">
        <h2>{SCOPE_COPY.groundRulesTitle}</h2>
        <p className="section-help">{SCOPE_COPY.groundRulesHelp}</p>
        <ul className="ground-rules">
          {groundRuleKeys.map((key) => {
            const editable = assumedBecauseSkipped[key];
            const fieldId = `ground-rule-${key}`;
            return (
              <li key={key} className="ground-rule-item">
                {/* The editable control lives outside this label: nesting it
                    would make every keystroke toggle the confirmation. */}
                <label className="ground-rule-confirm">
                  <input
                    type="checkbox"
                    checked={confirmations[key] === true}
                    onChange={() => toggleConfirmation(key)}
                  />
                  <span className="ground-rule-label">{GROUND_RULE_LABELS[key]}</span>
                  {!editable && (
                    <span className="ground-rule-value">{groundRuleValues[key]}</span>
                  )}
                </label>
                {editable && (
                  <div className="ground-rule-edit">
                    <label htmlFor={fieldId} className="sr-only">
                      {GROUND_RULE_LABELS[key]}
                    </label>
                    {key === GROUND_RULE_KEYS.deadline ? (
                      <input
                        id={fieldId}
                        type="date"
                        className="ground-rule-input"
                        value={groundRuleRawValues[key]}
                        onChange={(e) => editGroundRule(key, e.target.value)}
                      />
                    ) : (
                      <select
                        id={fieldId}
                        className="ground-rule-input"
                        value={groundRuleRawValues[key]}
                        onChange={(e) => editGroundRule(key, e.target.value)}
                      >
                        {(key === GROUND_RULE_KEYS.riskTolerance
                          ? RISK_TOLERANCE_OPTIONS
                          : REVERSIBILITY_OPTIONS
                        ).map((opt) => (
                          <option key={opt.value} value={opt.value}>{opt.label}</option>
                        ))}
                      </select>
                    )}
                    <span className="assumed-mark">
                      {SCOPE_COPY.declaredAssumptionLabel} {SCOPE_COPY.assumedEditableNote}
                    </span>
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      {/* ── Effort & limits ───────────────────────────────────────────────── */}
      <section className="scope-section">
        <h2>{SCOPE_COPY.effortTitle}</h2>
        <p className="effort-summary">
          {effortProfile.label} — {effortProfile.timeRange}. {effortProfile.blurb}
        </p>
        <p className="effort-limits-intro">{EFFORT_LIMITS_INTRO}</p>
        <div className="effort-columns">
          <div className="effort-column">
            <h3>What this will do</h3>
            <ul>
              {WHAT_IT_CAN_DO.map((line, i) => <li key={i}>{line}</li>)}
            </ul>
          </div>
          <div className="effort-column">
            <h3>{SCOPE_COPY.whatItCantDoTitle}</h3>
            <ul>
              {WHAT_IT_CANT_DO.map((line, i) => <li key={i}>{line}</li>)}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Signature ─────────────────────────────────────────────────────── */}
      <section className="scope-section signature-block">
        <h2>{SCOPE_COPY.signatureTitle}</h2>
        <p className="section-help">{SCOPE_COPY.signHelp}</p>
        {revisionNeeded && (
          <p className="revision-pending">
            You have edits to the framing. Signing will request a revised framing first,
            then re-present this sheet for a clean sign.
          </p>
        )}
        <button
          type="button"
          className="primary-action"
          onClick={handleSign}
          disabled={!canSign}
        >
          {submitting ? "Working…" : SCOPE_COPY.signButton}
        </button>
        <p className="section-help">{SCOPE_COPY.saveLaterHelp}</p>
        <button type="button" className="secondary-action" onClick={handleSaveLater}>
          {SCOPE_COPY.saveLaterButton}
        </button>
        {!allGroundRulesConfirmed(sheetState) && (
          <p className="screen-help" role="note">
            Confirm every ground rule above to enable signing.
          </p>
        )}
      </section>

      <p className="back-link">
        <Link to={`/cases/${caseId}`}>Back to the case</Link>
      </p>
    </div>
  );
}
