#!/usr/bin/env python3
"""Workflow benchmark runner for SPEC-021.

Runs each benchmark scenario through the full multi-agent pipeline unattended
(pre-seeded approvals from the scenario YAML) and copies the final package +
metrics to ``benchmarks/results/<case>/workflow/``.

This is the workflow side of the baseline-vs-workflow comparison.  The baseline
side is ``scripts/run_baseline.py``.

Usage:
    uv run python scripts/run_benchmarks.py --scenario benchmarks/cases/scenario-01-*.yaml
    uv run python scripts/run_benchmarks.py --all
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.case_store import Case  # noqa: E402
from orchestrator.pipeline import DEFAULT_BUDGET, SMALL_BUDGET, run_scenario  # noqa: E402
from orchestrator.state_machine import CaseStage  # noqa: E402

# Reuse the scoring and metrics extraction from run_e2e_eval.
from scripts.run_e2e_eval import _extract_metrics, _score_case  # noqa: E402

_BUDGET_PROFILES: dict[str, Any] = {
    "small": SMALL_BUDGET,
    "default": DEFAULT_BUDGET,
}


def _load_scenario(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML mapping at {path}")
    return loaded


def _copy_final_package(case: Case, dest: Path) -> None:
    """Copy the case's final artifacts to the results directory."""
    dest.mkdir(parents=True, exist_ok=True)

    # Copy final recommendation
    final_md = case.root / "outputs" / "final_recommendation.md"
    if final_md.exists():
        shutil.copy2(final_md, dest / "final_recommendation.md")

    # Copy final recommendation YAML
    final_yaml = case.root / "outputs" / "final_recommendation.yaml"
    if final_yaml.exists():
        shutil.copy2(final_yaml, dest / "final_recommendation.yaml")

    # Copy decision spec
    spec = case.root / "shared" / "decision_spec.yaml"
    if spec.exists():
        shutil.copy2(spec, dest / "decision_spec.yaml")

    # Copy evidence directory
    evidence_dir = case.root / "shared" / "evidence"
    if evidence_dir.exists():
        shutil.copytree(evidence_dir, dest / "evidence", dirs_exist_ok=True)

    # Copy audit log
    audit = case.root / "audit.jsonl"
    if audit.exists():
        shutil.copy2(audit, dest / "audit.jsonl")


def run_one_workflow(
    scenario_path: Path,
    *,
    output_dir: Path,
    cases_root: Path | None = None,
) -> dict[str, Any]:
    """Run a single scenario through the full workflow and save results."""
    scenario = _load_scenario(scenario_path)
    prompt = str(scenario["prompt"]).strip()
    slug = str(scenario.get("slug", scenario_path.stem))
    scenario_id = str(scenario.get("id", scenario_path.stem))
    title = str(scenario.get("title", scenario_path.name))
    budget_profile = str(scenario.get("budget_profile", "small"))

    print(f"\n{'=' * 60}")
    print(f"Workflow: {title}")
    print(f"Prompt: {prompt[:100]}...")
    print(f"{'=' * 60}")

    budget = _BUDGET_PROFILES.get(budget_profile, SMALL_BUDGET)
    start_time = time.time()

    try:
        case, state = run_scenario(
            prompt,
            slug=slug,
            budget_config=budget,
            cases_root=cases_root,
        )
        elapsed = time.time() - start_time
        final_stage = state.stage.value

        metrics = _extract_metrics(case)
        scoring = _score_case(case, scenario)

        # Copy final package to results
        workflow_dir = output_dir / scenario_id / "workflow"
        _copy_final_package(case, workflow_dir)

        summary: dict[str, Any] = {
            "scenario_id": scenario_id,
            "scenario_title": title,
            "type": "workflow",
            "case_id": case.root.name,
            "final_stage": final_stage,
            "elapsed_seconds": round(elapsed, 1),
            "metrics": metrics,
            "scoring": scoring,
            "success": final_stage == CaseStage.DONE.value,
        }

        (workflow_dir / "summary.json").write_text(
            json.dumps(summary, indent=2, ensure_ascii=False, default=str) + "\n",
            encoding="utf-8",
        )

    except Exception as exc:
        elapsed = time.time() - start_time
        summary = {
            "scenario_id": scenario_id,
            "scenario_title": title,
            "type": "workflow",
            "error": str(exc),
            "elapsed_seconds": round(elapsed, 1),
            "success": False,
        }

    print(f"\nResult: {'SUCCESS' if summary.get('success') else 'FAILED'}")
    print(f"  Stage: {summary.get('final_stage', 'error')}")
    print(f"  Elapsed: {summary.get('elapsed_seconds', 0):.1f}s")
    if "metrics" in summary:
        m = summary["metrics"]
        print(f"  Invocations: {m['total_invocations']} ({m['successful_invocations']} ok)")
        print(f"  Tokens: {m['total_input_tokens']:,} in / {m['total_output_tokens']:,} out")
    if "scoring" in summary:
        s = summary["scoring"]
        print(f"  Overall score: {s['overall_score']:.2f} / 2.0")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run workflow benchmarks")
    parser.add_argument(
        "--scenario",
        type=Path,
        help="Path to a single scenario YAML",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run all scenarios in benchmarks/cases/",
    )
    parser.add_argument(
        "--cases-root",
        type=Path,
        default=REPO_ROOT / "cases",
        help="Root directory for case data",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "benchmarks" / "results",
        help="Output directory for results",
    )
    args = parser.parse_args()

    if not args.scenario and not args.all:
        parser.error("Specify --scenario or --all")

    if args.all:
        scenarios = sorted((REPO_ROOT / "benchmarks" / "cases").glob("scenario-*.yaml"))
    else:
        scenarios = [args.scenario]

    if not scenarios:
        print("No scenarios found!")
        return

    print(f"Running {len(scenarios)} workflow benchmark(s)...")

    results: list[dict[str, Any]] = []
    for scenario_path in scenarios:
        result = run_one_workflow(
            scenario_path,
            output_dir=args.output,
            cases_root=args.cases_root,
        )
        results.append(result)

    # Write combined summary
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "workflow_summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    print(f"\n\n{'=' * 60}")
    print("WORKFLOW BENCHMARK SUMMARY")
    print(f"{'=' * 60}")
    print(f"{'Scenario':<30} {'Stage':<15} {'Score':>6} {'Time':>8}")
    print("-" * 65)
    for r in results:
        name = r.get("scenario_id", "?")[:28]
        stage = r.get("final_stage", "error")[:13]
        score = r.get("scoring", {}).get("overall_score", 0.0)
        elapsed = r.get("elapsed_seconds", 0)
        print(f"{name:<30} {stage:<15} {score:>6.2f} {elapsed:>7.1f}s")
    print("-" * 65)

    total_score = sum(r.get("scoring", {}).get("overall_score", 0.0) for r in results)
    avg_score = total_score / len(results) if results else 0
    print(f"\nAverage score: {avg_score:.2f} / 2.0")
    print(f"Results saved to: {summary_path}")


if __name__ == "__main__":
    main()
