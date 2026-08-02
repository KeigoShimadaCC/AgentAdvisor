"""Forecast calibration over recorded case outcomes.

Brier score of the headline outcome probability against the realized result. With a
handful of cases this number is noise, so the sample size is always reported next to
it and it never influences a live case.
"""

from __future__ import annotations

from orchestrator.artifacts import CalibrationSummary, OutcomeRecord

MIN_MEANINGFUL_SAMPLE = 5


def brier_score(forecasts: list[tuple[float, bool]]) -> float | None:
    """Mean squared error between forecast probabilities and binary outcomes."""
    if not forecasts:
        return None
    total = sum(
        (probability - (1.0 if realized else 0.0)) ** 2 for probability, realized in forecasts
    )
    return round(total / len(forecasts), 6)


def summarize_calibration(outcomes: list[OutcomeRecord]) -> CalibrationSummary:
    forecasts = [(record.forecast_probability, record.realized) for record in outcomes]
    score = brier_score(forecasts)

    if not forecasts:
        return CalibrationSummary(
            sample_size=0,
            interpretation=(
                "No outcomes recorded yet, so the system's calibration is unknown. Record "
                "realized outcomes with scripts/record_outcome.py to start measuring it."
            ),
        )

    mean_forecast = round(sum(probability for probability, _ in forecasts) / len(forecasts), 4)
    mean_realized = round(sum(1.0 for _, realized in forecasts if realized) / len(forecasts), 4)

    if len(forecasts) < MIN_MEANINGFUL_SAMPLE:
        interpretation = (
            f"Brier score {score} over only {len(forecasts)} outcome(s); this is noise, not a "
            "calibration estimate."
        )
    elif mean_forecast - mean_realized > 0.1:
        interpretation = (
            f"Brier score {score} over {len(forecasts)} outcomes; forecasts have run "
            "optimistic relative to realized results."
        )
    elif mean_realized - mean_forecast > 0.1:
        interpretation = (
            f"Brier score {score} over {len(forecasts)} outcomes; forecasts have run "
            "pessimistic relative to realized results."
        )
    else:
        interpretation = (
            f"Brier score {score} over {len(forecasts)} outcomes; mean forecast and mean "
            "realized rate are close."
        )

    return CalibrationSummary(
        sample_size=len(forecasts),
        brier_score=score,
        mean_forecast=mean_forecast,
        mean_realized=mean_realized,
        interpretation=interpretation,
    )
