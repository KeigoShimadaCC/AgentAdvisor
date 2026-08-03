#!/usr/bin/env python3
"""Single-agent baseline runner for benchmark comparison (SPEC-021).

Gives one strong model the same prompt the multi-agent workflow receives, asks
for a Section 16 formatted recommendation, and saves the output so it can be
scored against the workflow's result by the same rubric.

The baseline is a single-shot invocation: no framing, no evidence gathering,
no adversarial challenge, no structured artifacts.  The model gets the prompt
and the output template, nothing else.

Usage:
    uv run python scripts/run_baseline.py --scenario benchmarks/cases/scenario-01-*.yaml
    uv run python scripts/run_baseline.py --all
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.backend import RoleInvocation, make_backend  # noqa: E402

# The Section 16 output template the baseline must follow, so format differences
# do not contaminate quality comparison (only substance differs).
_BASELINE_TEMPLATE = """\
You are a decision consultant. Analyze the following decision and produce a
recommendation in this exact format:

## Executive recommendation
A direct statement of the recommended action and timing.

## Decision confidence
A concise explanation of recommendation confidence, evidence confidence, and
major uncertainty.

## Alternatives considered
The serious alternatives and why they rank above or below one another.

## Key reasons
The small number of factors carrying the conclusion.

## Scenario analysis
Relevant upside, base, downside, and tail-risk scenarios, including
probabilities or ranges where defensible.

## Quantitative findings
Expected values, thresholds, simulations, or sensitivity results where useful.

## Strongest counterarguments
The material objections and how they were resolved or why they remain
unresolved.

## Critical assumptions
The assumptions that materially affect the recommendation.

## What would change the recommendation
Observable events, evidence, prices, terms, or thresholds that would cause a
different action.

## Next actions
Concrete steps, ordered by urgency or information value.

## Evidence and citations
Inline citations and a list of sources consulted.

---

Decision to analyze:

"""

# Strongest available model for the baseline (per backend).
_BASELINE_MODELS: dict[str, str] = {
    "cursor": "cursor-grok-4.5-low",
    "droid": "gpt-5.4",
}
_BASELINE_TIMEOUT_S = 600.0


def _load_scenario(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML mapping at {path}")
    return loaded


def run_one_baseline(
    scenario_path: Path,
    *,
    output_dir: Path,
    backend_name: str | None = None,
) -> dict[str, Any]:
    """Run a single baseline invocation and save results."""
    scenario = _load_scenario(scenario_path)
    prompt = str(scenario["prompt"]).strip()
    scenario_id = str(scenario.get("id", scenario_path.stem))
    title = str(scenario.get("title", scenario_path.name))

    print(f"\n{'=' * 60}")
    print(f"Baseline: {title}")
    print(f"Prompt: {prompt[:100]}...")
    print(f"{'=' * 60}")

    full_prompt = _BASELINE_TEMPLATE + prompt

    # Use a temporary workspace
    workspace = output_dir / scenario_id / "baseline" / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    backend = make_backend(backend_name)
    model = _BASELINE_MODELS.get(backend.name, _BASELINE_MODELS["cursor"])
    invocation = RoleInvocation(
        role="baseline",
        model=model,
        prompt=full_prompt,
        workspace=workspace,
        timeout_s=_BASELINE_TIMEOUT_S,
        read_only=False,
        # The baseline is a strong single agent with tool access. On droid this
        # maps to `--auto medium`; without it the agent hits a permission wall
        # ("Exec ended early: insufficient permission") and returns no report.
        allow_shell=True,
    )

    start_time = time.time()
    result = backend.run(invocation)
    elapsed = time.time() - start_time

    # Save output
    result_dir = output_dir / scenario_id / "baseline"
    result_dir.mkdir(parents=True, exist_ok=True)

    output_text = result.result_text or ""
    (result_dir / "recommendation.md").write_text(output_text, encoding="utf-8")

    usage = result.usage
    summary: dict[str, Any] = {
        "scenario_id": scenario_id,
        "scenario_title": title,
        "type": "baseline",
        "model": model,
        "status": result.status.value,
        "elapsed_seconds": round(elapsed, 1),
        "input_tokens": usage.input_tokens if usage else 0,
        "output_tokens": usage.output_tokens if usage else 0,
        "total_tokens": usage.total_tokens if usage else 0,
        "output_length": len(output_text),
        "has_recommendation": bool(output_text.strip()),
    }

    (result_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\nResult: {result.status.value}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"  Tokens: {summary['input_tokens']:,} in / {summary['output_tokens']:,} out")
    print(f"  Output: {summary['output_length']:,} chars")
    print(f"  Saved to: {result_dir}")

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run single-agent baseline for benchmarks")
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
        "--output",
        type=Path,
        default=REPO_ROOT / "benchmarks" / "results",
        help="Output directory for results",
    )
    parser.add_argument(
        "--backend",
        type=str,
        default=None,
        help="Backend to use (cursor or droid, defaults to AGENTADVISOR_BACKEND env)",
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

    backend = make_backend(args.backend)
    model = _BASELINE_MODELS.get(backend.name, _BASELINE_MODELS["cursor"])
    print(f"Running {len(scenarios)} baseline(s) with backend={backend.name}, model={model}...")

    results: list[dict[str, Any]] = []
    for scenario_path in scenarios:
        result = run_one_baseline(scenario_path, output_dir=args.output, backend_name=args.backend)
        results.append(result)

    # Write combined summary
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "baseline_summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"\n\n{'=' * 60}")
    print("BASELINE SUMMARY")
    print(f"{'=' * 60}")
    print(f"{'Scenario':<30} {'Status':<12} {'Time':>8} {'Tokens':>10}")
    print("-" * 65)
    for r in results:
        name = r.get("scenario_id", "?")[:28]
        status = r.get("status", "?")[:10]
        elapsed = r.get("elapsed_seconds", 0)
        tokens = r.get("total_tokens", 0)
        print(f"{name:<30} {status:<12} {elapsed:>7.1f}s {tokens:>10,}")
    print("-" * 65)
    print(f"\nResults saved to: {summary_path}")


if __name__ == "__main__":
    main()
