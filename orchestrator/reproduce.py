from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from orchestrator.artifacts import AnalysisResult

FLOAT_TOLERANCE = 1e-9


class ReproduceStatus(StrEnum):
    PASS = "pass"
    DIVERGED = "diverged"
    TIMEOUT = "timeout"


@dataclass(frozen=True, slots=True)
class DiffEntry:
    path: str
    expected: Any
    actual: Any
    reason: str


@dataclass(frozen=True, slots=True)
class ReproduceResult:
    status: ReproduceStatus
    diff: tuple[DiffEntry, ...] = ()
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    timeout_s: float | None = None

    def rejection_feedback(self) -> str:
        if self.status is ReproduceStatus.PASS:
            return "Reproducibility check passed."
        if self.status is ReproduceStatus.TIMEOUT:
            return f"Reproducibility check timed out after {self.timeout_s:.3f}s."

        lines = ["Reproducibility check diverged."]
        if self.returncode is not None:
            lines.append(f"Script return code: {self.returncode}.")
        if self.diff:
            lines.append("Diff:")
            for entry in self.diff:
                lines.append(
                    f"- {entry.path}: {entry.reason} "
                    f"(expected={entry.expected!r}, actual={entry.actual!r})"
                )
        if self.stderr:
            lines.append(f"stderr: {self.stderr.strip()}")
        return "\n".join(lines)

    def require_pass(self) -> None:
        if self.status is not ReproduceStatus.PASS:
            raise ValueError(self.rejection_feedback())


def _ensure_within_case(case_root: Path, candidate: Path, field_name: str) -> None:
    try:
        candidate.relative_to(case_root)
    except ValueError as exc:
        raise ValueError(f"{field_name} must resolve under case root.") from exc


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _coerce_output(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _append_diff(
    diffs: list[DiffEntry],
    *,
    path: str,
    expected: Any,
    actual: Any,
    reason: str,
) -> None:
    diffs.append(DiffEntry(path=path, expected=expected, actual=actual, reason=reason))


def _diff_values(
    expected: Any,
    actual: Any,
    *,
    path: str,
    diffs: list[DiffEntry],
    float_tolerance: float,
) -> None:
    if _is_number(expected) and _is_number(actual):
        expected_value = float(expected)
        actual_value = float(actual)
        if isinstance(expected, float) or isinstance(actual, float):
            if abs(expected_value - actual_value) > float_tolerance:
                _append_diff(
                    diffs,
                    path=path,
                    expected=expected,
                    actual=actual,
                    reason=f"float mismatch beyond tolerance {float_tolerance}",
                )
            return
        if expected != actual:
            _append_diff(
                diffs,
                path=path,
                expected=expected,
                actual=actual,
                reason="integer mismatch",
            )
        return

    if type(expected) is not type(actual):  # noqa: E721
        _append_diff(
            diffs,
            path=path,
            expected=expected,
            actual=actual,
            reason=f"type mismatch ({type(expected).__name__} != {type(actual).__name__})",
        )
        return

    if isinstance(expected, dict):
        expected_keys = set(expected.keys())
        actual_keys = set(actual.keys())
        for missing_key in sorted(expected_keys - actual_keys, key=str):
            _append_diff(
                diffs,
                path=f"{path}.{missing_key}",
                expected=expected[missing_key],
                actual=None,
                reason="missing key in actual",
            )
        for extra_key in sorted(actual_keys - expected_keys, key=str):
            _append_diff(
                diffs,
                path=f"{path}.{extra_key}",
                expected=None,
                actual=actual[extra_key],
                reason="unexpected key in actual",
            )
        for shared_key in sorted(expected_keys & actual_keys, key=str):
            _diff_values(
                expected[shared_key],
                actual[shared_key],
                path=f"{path}.{shared_key}",
                diffs=diffs,
                float_tolerance=float_tolerance,
            )
        return

    if isinstance(expected, list):
        if len(expected) != len(actual):
            _append_diff(
                diffs,
                path=path,
                expected=len(expected),
                actual=len(actual),
                reason="list length mismatch",
            )
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=False)):
            _diff_values(
                expected_item,
                actual_item,
                path=f"{path}[{index}]",
                diffs=diffs,
                float_tolerance=float_tolerance,
            )
        return

    if expected != actual:
        _append_diff(
            diffs,
            path=path,
            expected=expected,
            actual=actual,
            reason="value mismatch",
        )


def reproduce_analysis_result(
    *,
    case_root: Path,
    analysis_result: AnalysisResult,
    timeout_s: float = 30.0,
    float_tolerance: float = FLOAT_TOLERANCE,
) -> ReproduceResult:
    root = case_root.resolve()
    script_path = (root / analysis_result.script_path).resolve()
    results_path = (root / analysis_result.results_path).resolve()

    _ensure_within_case(root, script_path, "script_path")
    _ensure_within_case(root, results_path, "results_path")

    committed_text = results_path.read_text(encoding="utf-8")
    committed_payload = yaml.safe_load(committed_text)

    try:
        completed = subprocess.run(
            [sys.executable, script_path.name],
            cwd=script_path.parent,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        results_path.write_text(committed_text, encoding="utf-8")
        return ReproduceResult(
            status=ReproduceStatus.TIMEOUT,
            stdout=_coerce_output(exc.stdout),
            stderr=_coerce_output(exc.stderr),
            timeout_s=timeout_s,
        )

    regenerated_payload: Any
    if not results_path.exists():
        results_path.write_text(committed_text, encoding="utf-8")
        return ReproduceResult(
            status=ReproduceStatus.DIVERGED,
            diff=(
                DiffEntry(
                    path="$",
                    expected="results file present",
                    actual="results file missing",
                    reason="script did not produce results file",
                ),
            ),
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    regenerated_text = results_path.read_text(encoding="utf-8")
    regenerated_payload = yaml.safe_load(regenerated_text)
    results_path.write_text(committed_text, encoding="utf-8")

    diffs: list[DiffEntry] = []
    _diff_values(
        committed_payload,
        regenerated_payload,
        path="$",
        diffs=diffs,
        float_tolerance=float_tolerance,
    )
    if completed.returncode != 0:
        _append_diff(
            diffs,
            path="$",
            expected=0,
            actual=completed.returncode,
            reason="script exited with non-zero status",
        )

    if diffs:
        return ReproduceResult(
            status=ReproduceStatus.DIVERGED,
            diff=tuple(diffs),
            stdout=completed.stdout,
            stderr=completed.stderr,
            returncode=completed.returncode,
        )

    return ReproduceResult(
        status=ReproduceStatus.PASS,
        stdout=completed.stdout,
        stderr=completed.stderr,
        returncode=completed.returncode,
    )
