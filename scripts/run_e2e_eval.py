#!/usr/bin/env python3
"""Run benchmark scenarios end-to-end and score results.

Usage:
    uv run python scripts/run_e2e_eval.py --scenario benchmarks/cases/scenario-01-*.yaml
    uv run python scripts/run_e2e_eval.py --all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator.backend import BackendName, make_backend  # noqa: E402
from orchestrator.case_store import Case  # noqa: E402
from orchestrator.pipeline import SMALL_BUDGET, run_scenario  # noqa: E402


def _load_scenario(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected YAML mapping at {path}")
    return loaded


def _phase6_metrics(case: Case, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Counters for the structures Phase 6 introduced.

    The rubric predates them, so without these the before/after comparison would show
    only whether the new stages hurt the old score, not whether they did anything.
    """
    shared = case.root / "shared"

    issue_tree_path = shared / "issue_tree.yaml"
    leaf_count = 0
    node_count = 0
    if issue_tree_path.exists():
        tree = yaml.safe_load(issue_tree_path.read_text(encoding="utf-8")) or {}
        nodes = tree.get("nodes", [])
        node_count = len(nodes)
        parents = {node.get("parent_id") for node in nodes}
        leaf_count = sum(1 for node in nodes if node.get("node_id") not in parents)

    critique_path = shared / "evidence_critique.yaml"
    critique: dict[str, Any] = {}
    if critique_path.exists():
        critique = yaml.safe_load(critique_path.read_text(encoding="utf-8")) or {}

    premortem_path = shared / "premortem_report.yaml"
    failure_modes = 0
    if premortem_path.exists():
        report = yaml.safe_load(premortem_path.read_text(encoding="utf-8")) or {}
        failure_modes = len(report.get("failure_modes", []))

    gate_dir = shared / "gates"
    gate_reports = list(gate_dir.glob("*.yaml")) if gate_dir.exists() else []
    gate_blocks = 0
    gate_warns = 0
    for path in gate_reports:
        report = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for finding in report.get("findings", []):
            if finding.get("severity") == "block":
                gate_blocks += 1
            elif finding.get("severity") == "warn":
                gate_warns += 1

    thesis_dir = shared / "thesis"
    thesis_files = list(thesis_dir.glob("*.yaml")) if thesis_dir.exists() else []
    thesis_changes = 0
    for path in thesis_files:
        revision = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if revision.get("changed"):
            thesis_changes += 1

    divergence_path = shared / "track_divergence.yaml"
    track_agreement: bool | None = None
    if divergence_path.exists():
        divergence = yaml.safe_load(divergence_path.read_text(encoding="utf-8")) or {}
        track_agreement = divergence.get("agreement")

    worksheet_path = shared / "verification_worksheet.yaml"
    worksheet_items = 0
    if worksheet_path.exists():
        worksheet = yaml.safe_load(worksheet_path.read_text(encoding="utf-8")) or {}
        worksheet_items = len(worksheet.get("items", []))

    review_events = [e for e in events if e.get("event_type") == "review_evaluated"]
    resynthesis_count = sum(1 for e in review_events if not e.get("payload", {}).get("accepted"))

    return {
        "issue_tree_nodes": node_count,
        "issue_tree_leaves": leaf_count,
        "evidence_primary_share": critique.get("primary_source_share"),
        "evidence_authority_mean": critique.get("corpus_authority_mean"),
        "evidence_max_cluster_share": critique.get("max_cluster_share"),
        "evidence_independent_groups": critique.get("independent_group_count"),
        "evidence_gaps": len(critique.get("gaps", [])),
        "premortem_failure_modes": failure_modes,
        "gate_reports": len(gate_reports),
        "gate_blocking_findings": gate_blocks,
        "gate_warning_findings": gate_warns,
        "thesis_revisions": len(thesis_files),
        "thesis_changes": thesis_changes,
        "track_agreement": track_agreement,
        "verification_worksheet_items": worksheet_items,
        "resynthesis_cycles": resynthesis_count,
    }


def _extract_metrics(case: Case) -> dict[str, Any]:
    """Extract usage metrics from the case audit log."""
    audit_path = case.root / "audit.jsonl"
    if not audit_path.exists():
        return {"invocations": 0}

    events: list[dict[str, Any]] = []
    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            events.append(json.loads(line))

    invocations = [e for e in events if e.get("event_type") == "role_invocation_attempt"]
    successful = [e for e in invocations if e.get("payload", {}).get("status") == "ok"]
    failed = [e for e in invocations if e.get("payload", {}).get("status") != "ok"]

    total_input = sum(
        e.get("usage", {}).get("input_tokens", 0) for e in invocations if e.get("usage")
    )
    total_output = sum(
        e.get("usage", {}).get("output_tokens", 0) for e in invocations if e.get("usage")
    )
    total_cache = sum(
        e.get("usage", {}).get("cache_read_tokens", 0) for e in invocations if e.get("usage")
    )
    total_duration = sum(e.get("duration_ms", 0) for e in invocations)

    # Count artifacts
    evidence_count = len(list((case.root / "shared" / "evidence").glob("*.yaml")))
    assumption_count = len(list((case.root / "shared" / "assumptions").glob("*.yaml")))
    objection_count = len(list((case.root / "shared" / "objections").glob("*.yaml")))
    analysis_count = len(list((case.root / "analysis").glob("*.yaml")))
    task_count = len(list((case.root / "shared" / "tasks").glob("*.yaml")))

    has_final_rec = (case.root / "outputs" / "final_recommendation.md").exists()

    return {
        **_phase6_metrics(case, events),
        "total_invocations": len(invocations),
        "successful_invocations": len(successful),
        "failed_invocations": len(failed),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cache_read_tokens": total_cache,
        "total_duration_ms": total_duration,
        "evidence_records": evidence_count,
        "assumption_records": assumption_count,
        "objection_records": objection_count,
        "analysis_results": analysis_count,
        "task_records": task_count,
        "has_final_recommendation": has_final_rec,
    }


def _score_case(case: Case, scenario: dict[str, Any]) -> dict[str, Any]:
    """Score a case against the rubric (objective criteria only)."""
    scores: dict[str, Any] = {}

    # Check DecisionSpec
    decision_spec_path = case.root / "shared" / "decision_spec.yaml"
    if decision_spec_path.exists():
        spec = yaml.safe_load(decision_spec_path.read_text(encoding="utf-8"))
        alternatives = spec.get("alternatives", [])
        objectives = spec.get("objectives", [])
        constraints = spec.get("constraints", [])
        scores["dc-1"] = min(2, len(alternatives) // 3) if alternatives else 0
        scores["dc-2"] = (
            2 if objectives and constraints else (1 if objectives or constraints else 0)
        )
    else:
        scores["dc-1"] = 0
        scores["dc-2"] = 0

    # Check evidence
    evidence_dir = case.root / "shared" / "evidence"
    evidence_records = list(evidence_dir.glob("*.yaml")) if evidence_dir.exists() else []
    primary_count = 0
    with_citations = 0
    with_limitations = 0
    for path in evidence_records:
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        source_type = str(record.get("source_type", "")).lower()
        if any(
            k in source_type for k in ["regulatory", "filing", "official", "primary", "government"]
        ):
            primary_count += 1
        if record.get("source_url"):
            with_citations += 1
        limitations = record.get("limitations", [])
        if limitations:
            with_limitations += 1

    scores["eq-1"] = min(2, primary_count) if evidence_records else 0
    scores["eq-2"] = 2 if with_citations > 0 else 0
    scores["eq-3"] = 2 if with_limitations > 0 else 0

    # Check analysis
    analysis_dir = case.root / "analysis"
    analysis_files = list(analysis_dir.glob("*.yaml")) if analysis_dir.exists() else []
    has_sensitivity = False
    sensitivity_rows = 0
    for path in analysis_files:
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        table = record.get("sensitivity_table", [])
        if table:
            has_sensitivity = True
            sensitivity_rows = max(sensitivity_rows, len(table))

    scores["aq-1"] = 2 if has_sensitivity else (1 if analysis_files else 0)
    scores["aq-3"] = min(2, sensitivity_rows // 3) if sensitivity_rows else 0

    # Check objections
    objections_dir = case.root / "shared" / "objections"
    objection_files = list(objections_dir.glob("*.yaml")) if objections_dir.exists() else []
    scores["ar-1"] = min(2, len(objection_files) // 2) if objection_files else 0

    # Check traceability
    final_rec_path = case.root / "outputs" / "final_recommendation.md"
    if final_rec_path.exists():
        content = final_rec_path.read_text(encoding="utf-8")
        has_e_refs = bool(re.search(r"\[E-\d+\]", content))
        has_a_refs = bool(re.search(r"\[A-\d+\]", content))
        scores["tr-1"] = 2 if has_e_refs or has_a_refs else 0
    else:
        scores["tr-1"] = 0

    # Check audit completeness
    has_intake = (case.root / "shared" / "intake_record.yaml").exists()
    has_spec = (case.root / "shared" / "decision_spec.yaml").exists()
    has_prelim = (case.root / "shared" / "preliminary_recommendation.yaml").exists()
    has_final = (case.root / "outputs" / "final_recommendation.yaml").exists()
    complete_chain = has_intake and has_spec and has_prelim and has_final
    partial_chain = sum([has_intake, has_spec, has_prelim, has_final]) >= 3
    scores["tr-2"] = 2 if complete_chain else (1 if partial_chain else 0)

    # Calculate dimension averages
    dimension_map: dict[str, list[int]] = {
        "decision_completeness": ["dc-1", "dc-2"],
        "evidence_quality": ["eq-1", "eq-2", "eq-3"],
        "analytical_quality": ["aq-1", "aq-3"],
        "adversarial_robustness": ["ar-1"],
        "traceability": ["tr-1", "tr-2"],
    }

    dimension_scores: dict[str, float] = {}
    for dim, criteria in dimension_map.items():
        values = [scores.get(c, 0) for c in criteria]
        dimension_scores[dim] = sum(values) / len(values) if values else 0.0

    overall = sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.0

    return {
        "criterion_scores": scores,
        "dimension_scores": dimension_scores,
        "overall_score": round(overall, 3),
    }


def run_one_scenario(
    scenario_path: Path,
    *,
    cases_root: Path | None = None,
    backend_name: str | None = None,
) -> dict[str, Any]:
    """Run a single scenario end-to-end and return results."""
    scenario = _load_scenario(scenario_path)
    prompt = str(scenario["prompt"]).strip()
    slug = str(scenario.get("slug", scenario_path.stem))
    backend = make_backend(backend_name)

    print(f"\n{'=' * 60}")
    print(f"Scenario: {scenario.get('title', scenario_path.name)}")
    print(f"Prompt: {prompt[:100]}...")
    print(f"Backend: {backend.name}")
    print(f"{'=' * 60}")

    budget = SMALL_BUDGET
    start_time = time.time()

    try:
        case, state = run_scenario(
            prompt,
            slug=slug,
            budget_config=budget,
            backend=backend,
            cases_root=cases_root,
        )
        elapsed = time.time() - start_time
        final_stage = state.stage.value

        metrics = _extract_metrics(case)
        scoring = _score_case(case, scenario)

        result = {
            "scenario_id": scenario.get("id", scenario_path.stem),
            "scenario_title": scenario.get("title", scenario_path.name),
            "backend": backend.name,
            "case_id": case.root.name,
            "final_stage": final_stage,
            "elapsed_seconds": round(elapsed, 1),
            "metrics": metrics,
            "scoring": scoring,
            "success": final_stage == "done",
        }

    except Exception as exc:
        elapsed = time.time() - start_time
        result = {
            "scenario_id": scenario.get("id", scenario_path.stem),
            "scenario_title": scenario.get("title", scenario_path.name),
            "backend": backend.name,
            "error": str(exc),
            "elapsed_seconds": round(elapsed, 1),
            "success": False,
        }

    print(f"\nResult: {'SUCCESS' if result.get('success') else 'FAILED'}")
    print(f"  Stage: {result.get('final_stage', 'error')}")
    print(f"  Elapsed: {result.get('elapsed_seconds', 0):.1f}s")
    if "metrics" in result:
        m = result["metrics"]
        print(f"  Invocations: {m['total_invocations']} ({m['successful_invocations']} ok)")
        print(f"  Tokens: {m['total_input_tokens']} in / {m['total_output_tokens']} out")
        print(f"  Evidence: {m['evidence_records']}, Objections: {m['objection_records']}")
        print(f"  Analysis: {m['analysis_results']}, Tasks: {m['task_records']}")
        print(f"  Final recommendation: {m['has_final_recommendation']}")
    if "scoring" in result:
        s = result["scoring"]
        print(f"  Overall score: {s['overall_score']:.2f} / 2.0")
        for dim, score in s["dimension_scores"].items():
            print(f"    {dim}: {score:.2f}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run e2e benchmark scenarios")
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
    parser.add_argument(
        "--backend",
        choices=sorted(name.value for name in BackendName),
        default=None,
        help="Agent CLI to run roles on (defaults to AGENTADVISOR_BACKEND, else cursor)",
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

    print(f"Running {len(scenarios)} scenario(s)...")

    results: list[dict[str, Any]] = []
    for scenario_path in scenarios:
        result = run_one_scenario(
            scenario_path, cases_root=args.cases_root, backend_name=args.backend
        )
        results.append(result)

    # Write summary
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "e2e_summary.json"
    summary_path.write_text(
        json.dumps(results, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )

    # Print summary table
    print(f"\n\n{'=' * 60}")
    print("E2E EVALUATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"{'Scenario':<30} {'Stage':<15} {'Score':>6} {'Time':>8} {'Tokens':>10}")
    print("-" * 75)
    for r in results:
        name = r.get("scenario_id", "?")[:28]
        stage = r.get("final_stage", "error")[:13]
        score = r.get("scoring", {}).get("overall_score", 0.0)
        elapsed = r.get("elapsed_seconds", 0)
        tokens = r.get("metrics", {}).get("total_input_tokens", 0)
        print(f"{name:<30} {stage:<15} {score:>6.2f} {elapsed:>7.1f}s {tokens:>10,}")
    print("-" * 75)

    total_score = sum(r.get("scoring", {}).get("overall_score", 0.0) for r in results)
    avg_score = total_score / len(results) if results else 0
    print(f"\nAverage score: {avg_score:.2f} / 2.0")
    print(f"Results saved to: {summary_path}")


if __name__ == "__main__":
    main()
