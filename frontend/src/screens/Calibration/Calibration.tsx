import { useEffect, useState } from "react";
import { api, type CalibrationSummary } from "../../api/client";
import { Skeleton } from "../shared/Skeleton";
import { CaseCrumb } from "../shell/CaseCrumb";

/**
 * Below this the module itself calls the number noise, and so does this screen.
 * Kept in step with `MIN_MEANINGFUL_SAMPLE` in `orchestrator/calibration.py`.
 */
export const MIN_MEANINGFUL_SAMPLE = 5;

/**
 * The system's own track record (SPEC-051).
 *
 * `calibration.py` has existed since SPEC-025 — written, tested, and careful
 * about small samples — and nothing had ever served it to a user. A product
 * whose pitch is epistemic honesty was keeping its own forecasting record
 * private, which is the one number a user has most right to see.
 *
 * The interpretation string renders **verbatim**. The honesty is in the
 * wording: under five outcomes the module says "this is noise, not a
 * calibration estimate", and a screen that turned that into a confident dial
 * would undo the exact property the module was written to protect. So under
 * five outcomes this screen shows no headline score at all.
 */
export function Calibration() {
  const [summary, setSummary] = useState<CalibrationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getCalibration()
      .then(setSummary)
      .catch((e: { detail?: string; error?: string }) =>
        setError(e.detail ?? e.error ?? "Could not read the calibration record."),
      )
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Skeleton shape="sheet" label="Loading the calibration record" />;
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!summary) return <p>No data.</p>;

  const meaningful = summary.sample_size >= MIN_MEANINGFUL_SAMPLE;

  return (
    <div className="calibration">
      <CaseCrumb />
      <h2>How well calibrated is this system?</h2>
      <p className="screen-help">
        When a case forecasts an outcome and you later record what happened, that pair goes into
        this record. It is the system's own track record, and it is the one number you have most
        right to see.
      </p>

      {/* The interpretation is the answer, not a caption under a number. */}
      <p className="calibration-interpretation">{summary.interpretation}</p>

      <dl className="calibration-measures">
        <div className="calibration-measure">
          <dt>Outcomes recorded</dt>
          <dd>{summary.sample_size}</dd>
        </div>
        {meaningful && summary.brier_score != null && (
          <div className="calibration-measure">
            <dt>Brier score</dt>
            <dd>{summary.brier_score.toFixed(3)}</dd>
          </div>
        )}
        {meaningful && summary.mean_forecast != null && (
          <div className="calibration-measure">
            <dt>Mean forecast</dt>
            <dd>{Math.round(summary.mean_forecast * 100)}%</dd>
          </div>
        )}
        {meaningful && summary.mean_realized != null && (
          <div className="calibration-measure">
            <dt>Mean realised</dt>
            <dd>{Math.round(summary.mean_realized * 100)}%</dd>
          </div>
        )}
      </dl>

      {!meaningful && (
        <p className="calibration-withheld">
          The score is withheld until there are {MIN_MEANINGFUL_SAMPLE} recorded outcomes. Showing
          it earlier would present noise as a measurement, which is the failure this record exists
          to avoid.
        </p>
      )}
    </div>
  );
}
