from __future__ import annotations

from datetime import UTC, datetime

import pytest

from orchestrator.artifacts import OutcomeRecord
from orchestrator.calibration import brier_score, summarize_calibration


def _outcome(probability: float, realized: bool, index: int = 1) -> OutcomeRecord:
    return OutcomeRecord(
        recorded_at=datetime(2026, 8, 1, tzinfo=UTC),
        outcome_summary=f"Outcome {index} recorded by the user.",
        recommendation_followed=True,
        forecast_outcome_name="positive_return_12m",
        forecast_probability=probability,
        realized=realized,
    )


def test_perfect_forecasts_score_zero() -> None:
    assert brier_score([(1.0, True), (0.0, False)]) == 0.0


def test_maximally_wrong_forecasts_score_one() -> None:
    assert brier_score([(0.0, True), (1.0, False)]) == 1.0


def test_uninformative_half_forecasts_score_a_quarter() -> None:
    assert brier_score([(0.5, True), (0.5, False)]) == 0.25


def test_no_forecasts_returns_none_rather_than_zero() -> None:
    assert brier_score([]) is None


def test_empty_history_says_calibration_is_unknown() -> None:
    summary = summarize_calibration([])

    assert summary.sample_size == 0
    assert summary.brier_score is None
    assert "unknown" in summary.interpretation


def test_small_sample_is_labelled_noise() -> None:
    summary = summarize_calibration([_outcome(0.7, True, 1), _outcome(0.6, False, 2)])

    assert summary.sample_size == 2
    assert summary.brier_score is not None
    assert "noise" in summary.interpretation


def test_systematically_optimistic_history_is_called_out() -> None:
    outcomes = [_outcome(0.9, False, index) for index in range(1, 7)]
    summary = summarize_calibration(outcomes)

    assert summary.sample_size == 6
    assert summary.mean_forecast == pytest.approx(0.9)
    assert summary.mean_realized == pytest.approx(0.0)
    assert "optimistic" in summary.interpretation


def test_systematically_pessimistic_history_is_called_out() -> None:
    outcomes = [_outcome(0.1, True, index) for index in range(1, 7)]
    summary = summarize_calibration(outcomes)

    assert "pessimistic" in summary.interpretation


def test_well_calibrated_history_reports_agreement() -> None:
    outcomes = [_outcome(0.5, index % 2 == 0, index) for index in range(1, 9)]
    summary = summarize_calibration(outcomes)

    assert summary.mean_forecast == pytest.approx(0.5)
    assert summary.mean_realized == pytest.approx(0.5)
    assert "close" in summary.interpretation
