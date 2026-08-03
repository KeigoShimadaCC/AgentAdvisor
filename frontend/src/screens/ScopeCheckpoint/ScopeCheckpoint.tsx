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
} from "./sheetPayload";

/** Map a backend effort/depth value to a UI EffortKey. */
function effortKeyFromDepth(depth: string | null | undefined): EffortKey {
  if (depth === "light") return "quick";
  if (depth === "deep") return "deep";
  return "standard";
}

/** Determine the origin of an option relative to the intake record. */
function optionOrigin(option: string, intakeOptions: string[] | null | undefined): OptionOrigin {
  if (!intakeOptions) return "added-by-analysis";
  return intakeOptions.some((o) => o.trim().toLowerCase() === option.trim().toLowerCase())
    ? "yours"
    : "added-by-analysis";
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
  const [optionAnnotations, setOptionAnnotations] = useState<Record<number, string>>({});
  const [newOption, setNewOption] = useState("");
  const [excludedQuestions, setExcludedQuestions] = useState<Set<string>>(new Set());
  const [confirmations, setConfirmations] = useState<Record<string, boolean>>({});
  const [revisionNotice, setRevisionNotice] = useState<string | null>(null);

  // Track the original restatement so we can detect edits.
  const [originalRestatement, setOriginalRestatement] = useState("");

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

  // Ground-rule values + assumed-because-skipped detection.
  const groundRuleValues: Record<string, string> = {
    [GROUND_RULE_KEYS.deadline]: spec?.deadline ?? "",
    [GROUND_RULE_KEYS.riskTolerance]: riskToleranceLabel(spec?.risk_tolerance),
    [GROUND_RULE_KEYS.reversibility]: reversibilityLabel(spec?.reversibility),
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
    confirmations,
    groundRuleKeys,
    clarificationAnswers: {},
  };

  const revisionNeeded = needsRevision(sheetState, originalRestatement);
  const canSign = allGroundRulesConfirmed(sheetState) && !submitting;

  // ── Mutations ─────────────────────────────────────────────────────────────
  function removeOption(index: number) {
    setOptions((prev) => prev.filter((_, i) => i !== index));
    setOptionAnnotations((prev) => {
      const next: Record<number, string> = {};
      for (const [k, v] of Object.entries(prev)) {
        const idx = Number(k);
        if (idx < index) next[idx] = v;
        else if (idx > index) next[idx - 1] = v;
      }
      return next;
    });
  }

  function annotateOption(index: number, text: string) {
    setOptionAnnotations((prev) => ({ ...prev, [index]: text }));
  }

  function addOption() {
    const text = newOption.trim();
    if (!text) return;
    setOptions((prev) => [...prev, text]);
    setNewOption("");
  }

  function toggleQuestion(q: string) {
    setExcludedQuestions((prev) => {
      const next = new Set(prev);
      if (next.has(q)) next.delete(q);
      else next.add(q);
      return next;
    });
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
            const origin = optionOrigin(opt, intakeOptions);
            return (
              <li key={`${opt}-${i}`} className="option-row">
                <span className={`option-origin origin-${origin}`} aria-label={OPTION_ORIGIN_LABELS[origin]}>
                  {OPTION_ORIGIN_LABELS[origin]}
                </span>
                <span className="option-text">{opt}</span>
                {optionAnnotations[i] && (
                  <span className="option-annotation">{optionAnnotations[i]}</span>
                )}
                <button
                  type="button"
                  className="link-button"
                  onClick={() => removeOption(i)}
                  aria-label={`Remove option: ${opt}`}
                >
                  Remove
                </button>
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

      {/* ── Ground rules ──────────────────────────────────────────────────── */}
      <section className="scope-section">
        <h2>{SCOPE_COPY.groundRulesTitle}</h2>
        <p className="section-help">{SCOPE_COPY.groundRulesHelp}</p>
        <ul className="ground-rules">
          {groundRuleKeys.map((key) => (
            <li key={key} className="ground-rule-item">
              <label>
                <input
                  type="checkbox"
                  checked={confirmations[key] === true}
                  onChange={() => toggleConfirmation(key)}
                />
                <span className="ground-rule-label">{GROUND_RULE_LABELS[key]}</span>
                <span className="ground-rule-value">{groundRuleValues[key]}</span>
                {assumedBecauseSkipped[key] && (
                  <span className="assumed-mark">
                    {SCOPE_COPY.declaredAssumptionLabel} {SCOPE_COPY.assumedEditableNote}
                  </span>
                )}
              </label>
            </li>
          ))}
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
