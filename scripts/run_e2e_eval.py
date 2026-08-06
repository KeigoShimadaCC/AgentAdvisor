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
from collections import defaultdict
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


def _phase8_metrics(case: Case, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Counters for the structures Phase 8 introduced.

    Same reasoning as ``_phase6_metrics``: the legacy rubric cannot see any of this, so
    without these columns the comparison would show only whether the new stages hurt the
    old score, never whether they did anything. Every legacy criterion is computed
    unchanged so the before/after columns stay directly comparable to the 1.96 baseline.
    """
    shared = case.root / "shared"
    outputs = case.root / "outputs"

    def _load(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

    spec = _load(shared / "decision_spec.yaml")
    final = _load(outputs / "final_recommendation.yaml")

    # ── SPEC-038: value model ────────────────────────────────────────────────
    weights = spec.get("objective_weights") or {}
    assessments = final.get("alternatives_considered", [])
    scored_alternatives = [a for a in assessments if a.get("objective_scores")]
    score_coverage = len(scored_alternatives) / len(assessments) if assessments else None

    # ── SPEC-039: independent review and limitations ─────────────────────────
    independent = _load(outputs / "independent_review.yaml")
    limitations = final.get("limitations", [])

    # ── SPEC-040: competing hypotheses ───────────────────────────────────────
    matrix = _load(shared / "ach_matrix.yaml")
    ach_alternatives = matrix.get("alternatives", [])
    ach_evidence = matrix.get("evidence_ids", [])
    cells = matrix.get("cells", [])
    expected_cells = len(ach_alternatives) * len(ach_evidence)
    # Diagnosticity is recomputed rather than read: the artifact stores raw scores, and
    # recomputing keeps this scorer honest if the weighting ever changes.
    zero_diagnosticity = 0
    if cells:
        by_evidence: dict[str, set[str]] = defaultdict(set)
        for cell in cells:
            by_evidence[cell.get("evidence_id", "")].add(cell.get("consistency", ""))
        zero_diagnosticity = sum(1 for values in by_evidence.values() if len(values) == 1)

    # ── SPEC-041: action plan executability ──────────────────────────────────
    actions = final.get("next_actions", [])
    with_first_step = sum(1 for a in actions if (a.get("first_step") or "").strip())
    placeholder_owners = sum(
        1
        for a in actions
        if (a.get("owner") or "").strip().lower() in {"tbd", "unknown", "n/a", "someone"}
    )

    # ── SPEC-042: monitoring coverage ────────────────────────────────────────
    plan = _load(outputs / "monitoring_plan.yaml")
    indicators = plan.get("indicators", [])
    premortem = _load(shared / "premortem_report.yaml")
    available_indicators = sum(
        len(mode.get("leading_indicators", [])) for mode in premortem.get("failure_modes", [])
    ) + len(final.get("recommendation_change_triggers", []))

    # ── SPEC-043: private evidence ───────────────────────────────────────────
    evidence_dir = shared / "evidence"
    private_records = 0
    total_records = 0
    if evidence_dir.exists():
        for path in evidence_dir.glob("*.yaml"):
            record = _load(path)
            total_records += 1
            if record.get("source_type") == "user_document":
                private_records += 1

    # Per-role failure accounting. The ACH matrix is the largest structured output any
    # role produces, so its reliability is reported separately rather than averaged in.
    role_failures: dict[str, int] = defaultdict(int)
    for event in events:
        if event.get("event_type") != "role_invocation_attempt":
            continue
        payload = event.get("payload", {})
        if payload.get("status") not in {None, "ok"}:
            role_failures[str(payload.get("actor") or event.get("actor") or "unknown")] += 1

    skipped = {
        e.get("event_type")
        for e in events
        if e.get("event_type") in {"ach_skipped", "independent_review_skipped"}
    }

    return {
        # SPEC-038
        "value_model_present": bool(weights),
        "value_model_objective_count": len(weights),
        "value_model_score_coverage": score_coverage,
        # SPEC-039
        "independent_review_verdict": independent.get("verdict"),
        "independent_review_unsupported_claims": len(
            independent.get("unsupported_claims", []) or []
        ),
        "limitations_count": len(limitations),
        # SPEC-040
        "ach_alternatives": len(ach_alternatives),
        "ach_evidence_scored": len(ach_evidence),
        "ach_evidence_excluded": len(matrix.get("excluded_evidence_ids", []) or []),
        "ach_matrix_complete": bool(cells) and len(cells) == expected_cells,
        "ach_zero_diagnosticity_records": zero_diagnosticity,
        "ach_skipped": "ach_skipped" in skipped,
        "ach_role_failures": role_failures.get("ach", 0),
        # SPEC-041
        "next_action_count": len(actions),
        "next_actions_with_first_step": with_first_step,
        "next_actions_placeholder_owner": placeholder_owners,
        # SPEC-042
        "monitoring_indicators": len(indicators),
        "monitoring_indicators_available": available_indicators,
        "monitoring_coverage": (
            len(indicators) / available_indicators if available_indicators else None
        ),
        "monitoring_mitigations": len(plan.get("mitigations", []) or []),
        "monitoring_concretized": plan.get("concretized"),
        # SPEC-043
        "private_evidence_records": private_records,
        "private_evidence_share": (private_records / total_records if total_records else None),
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
        **_phase8_metrics(case, events),
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


def _score_phase8(case: Case, metrics: dict[str, Any]) -> dict[str, int]:
    """Objective scores for the Phase 8 criteria, from the metrics already extracted."""
    scores: dict[str, int] = {}

    # ── value_model_binding ──────────────────────────────────────────────────
    if not metrics.get("value_model_present"):
        scores["vm-1"] = 0
        scores["vm-2"] = 0
    else:
        coverage = metrics.get("value_model_score_coverage") or 0.0
        scores["vm-1"] = 2 if coverage >= 1.0 else (1 if coverage > 0 else 0)
        # The rank-divergence gate finding is the objective signal: no finding means the
        # weighted and stated rankings agreed.
        gates = _gate_check_ids(case)
        diverged = "value_model.rank_divergence" in gates
        if not diverged:
            scores["vm-2"] = 2
        else:
            final = _load_yaml(case.root / "outputs" / "final_recommendation.yaml")
            reasons = " ".join(final.get("key_reasons", [])).lower()
            acknowledged = any(
                phrase in reasons for phrase in ("weight", "objective", "tradeoff", "trade-off")
            )
            scores["vm-2"] = 1 if acknowledged else 0

    # ── independent_review ───────────────────────────────────────────────────
    verdict = metrics.get("independent_review_verdict")
    if verdict is None:
        scores["ir-1"] = 0
    else:
        independent = _load_yaml(case.root / "outputs" / "independent_review.yaml")
        reasoning = str(independent.get("reasoning", ""))
        # A bare concur with no derivation is the failure mode this role exists to avoid.
        scores["ir-1"] = 2 if len(reasoning.split()) >= 25 else 1

    limitations = metrics.get("limitations_count", 0)
    scores["ir-2"] = 2 if limitations >= 2 else (1 if limitations == 1 else 0)

    # ── disconfirmation ──────────────────────────────────────────────────────
    if not metrics.get("ach_evidence_scored"):
        scores["dq-1"] = 0
        scores["dq-2"] = 0
    else:
        spec = _load_yaml(case.root / "shared" / "decision_spec.yaml")
        covered = metrics.get("ach_alternatives", 0) >= len(spec.get("alternatives", []) or [])
        scores["dq-1"] = 2 if metrics.get("ach_matrix_complete") and covered else 1

        scored = metrics.get("ach_evidence_scored", 0)
        uninformative = metrics.get("ach_zero_diagnosticity_records", 0)
        discriminating = (scored - uninformative) / scored if scored else 0.0
        scores["dq-2"] = 2 if discriminating > 0.5 else (1 if discriminating > 0 else 0)

    # ── commitment_to_action ─────────────────────────────────────────────────
    actions = metrics.get("next_action_count", 0)
    if not actions:
        scores["ca-1"] = 0
    else:
        complete = (
            metrics.get("next_actions_with_first_step", 0) == actions
            and metrics.get("next_actions_placeholder_owner", 0) == 0
        )
        scores["ca-1"] = 2 if complete else 1

    indicators = metrics.get("monitoring_indicators", 0)
    if not indicators:
        scores["ca-2"] = 0
    else:
        concretized = bool(metrics.get("monitoring_concretized"))
        linked = metrics.get("monitoring_mitigations", 0) > 0
        scores["ca-2"] = 2 if concretized and linked else 1

    return scores


def _score_phase6(case: Case, metrics: dict[str, Any]) -> dict[str, int]:
    """Objective scores for the Phase 6 criteria, from the metrics already extracted.

    SPEC-026's scope called for these rubric criteria alongside the metrics; the
    2026-08-06 spec sweep found only the metrics half existed and added this scorer.
    Every band is defined over ``_phase6_metrics`` output or the artifact files those
    metrics were drawn from, so the scoring stays reproducible from the case alone.
    """
    scores: dict[str, int] = {}

    # ── assumption_ledger_coverage ─────────────────────────────────────────
    assumptions = metrics.get("assumption_records", 0)
    scores["al-1"] = 2 if assumptions >= 5 else (1 if assumptions >= 1 else 0)

    assumptions_dir = case.root / "shared" / "assumptions"
    rated = 0
    total = 0
    if assumptions_dir.exists():
        for path in assumptions_dir.glob("*.yaml"):
            record = _load_yaml(path)
            if not record:
                continue
            total += 1
            if record.get("materiality") in {"high", "medium", "low"}:
                rated += 1
    if total == 0:
        scores["al-2"] = 0
    else:
        scores["al-2"] = 2 if rated == total else (1 if rated else 0)

    # ── evidence_authority ─────────────────────────────────────────────────
    authority_mean = metrics.get("evidence_authority_mean")
    if authority_mean is None:
        scores["ea-1"] = 0
    else:
        scores["ea-1"] = 2 if authority_mean >= 0.7 else (1 if authority_mean >= 0.4 else 0)

    cluster_share = metrics.get("evidence_max_cluster_share")
    if cluster_share is None:
        scores["ea-2"] = 0
    else:
        scores["ea-2"] = 2 if cluster_share <= 0.4 else (1 if cluster_share <= 0.6 else 0)

    # ── issue_tree_coverage ────────────────────────────────────────────────
    leaves = metrics.get("issue_tree_leaves", 0)
    scores["it-1"] = 2 if leaves >= 3 else (1 if leaves >= 1 else 0)

    tasks_dir = case.root / "shared" / "tasks"
    linked = 0
    total_tasks = 0
    if tasks_dir.exists():
        for path in tasks_dir.glob("*.yaml"):
            task = _load_yaml(path)
            if not task:
                continue
            total_tasks += 1
            if task.get("issue_node_id"):
                linked += 1
    if total_tasks == 0:
        scores["it-2"] = 0
    else:
        scores["it-2"] = 2 if linked / total_tasks >= 0.5 else (1 if linked else 0)

    # ── premortem_quality ──────────────────────────────────────────────────
    failure_mode_count = metrics.get("premortem_failure_modes", 0)
    scores["pm-1"] = 2 if failure_mode_count >= 3 else (1 if failure_mode_count >= 1 else 0)

    premortem = _load_yaml(case.root / "shared" / "premortem_report.yaml")
    failure_modes = premortem.get("failure_modes", [])
    if not failure_modes:
        scores["pm-2"] = 0
    else:
        with_indicators = sum(1 for mode in failure_modes if mode.get("leading_indicators"))
        scores["pm-2"] = (
            2 if with_indicators == len(failure_modes) else (1 if with_indicators else 0)
        )

    # ── verification_depth ─────────────────────────────────────────────────
    worksheet_items = metrics.get("verification_worksheet_items", 0)
    scores["vd-1"] = 2 if worksheet_items >= 5 else (1 if worksheet_items >= 1 else 0)

    gate_reports = metrics.get("gate_reports", 0)
    scores["vd-2"] = 2 if gate_reports >= 3 else (1 if gate_reports >= 1 else 0)

    # ── thesis_evolution ───────────────────────────────────────────────────
    revisions = metrics.get("thesis_revisions", 0)
    scores["te-1"] = 2 if revisions >= 2 else (1 if revisions == 1 else 0)

    if metrics.get("track_agreement") is not None:
        scores["te-2"] = 2
    elif (case.root / "shared" / "track_divergence.yaml").exists():
        scores["te-2"] = 1
    else:
        scores["te-2"] = 0

    return scores


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _gate_check_ids(case: Case) -> set[str]:
    gate_dir = case.root / "shared" / "gates"
    found: set[str] = set()
    if not gate_dir.exists():
        return found
    for path in gate_dir.glob("*.yaml"):
        report = _load_yaml(path)
        for finding in report.get("findings", []):
            check_id = finding.get("check_id")
            if check_id:
                found.add(str(check_id))
    return found


def _score_case(
    case: Case, scenario: dict[str, Any], metrics: dict[str, Any] | None = None
) -> dict[str, Any]:
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
    # Legacy dimensions, computed identically to the pre-Phase-8 scorer so the
    # before/after columns stay comparable to the 2026-08-03 baseline of 1.96.
    legacy_map: dict[str, list[str]] = {
        "decision_completeness": ["dc-1", "dc-2"],
        "evidence_quality": ["eq-1", "eq-2", "eq-3"],
        "analytical_quality": ["aq-1", "aq-3"],
        "adversarial_robustness": ["ar-1"],
        "traceability": ["tr-1", "tr-2"],
    }
    phase6_map: dict[str, list[str]] = {
        "assumption_ledger_coverage": ["al-1", "al-2"],
        "evidence_authority": ["ea-1", "ea-2"],
        "issue_tree_coverage": ["it-1", "it-2"],
        "premortem_quality": ["pm-1", "pm-2"],
        "verification_depth": ["vd-1", "vd-2"],
        "thesis_evolution": ["te-1", "te-2"],
    }
    phase8_map: dict[str, list[str]] = {
        "value_model_binding": ["vm-1", "vm-2"],
        "independent_review": ["ir-1", "ir-2"],
        "disconfirmation": ["dq-1", "dq-2"],
        "commitment_to_action": ["ca-1", "ca-2"],
    }

    if metrics is not None:
        scores.update(_score_phase6(case, metrics))
        scores.update(_score_phase8(case, metrics))

    def _dimension_scores(mapping: dict[str, list[str]]) -> dict[str, float]:
        result: dict[str, float] = {}
        for dim, criteria in mapping.items():
            values = [scores.get(c, 0) for c in criteria]
            result[dim] = sum(values) / len(values) if values else 0.0
        return result

    legacy_scores = _dimension_scores(legacy_map)
    legacy_overall = sum(legacy_scores.values()) / len(legacy_scores) if legacy_scores else 0.0

    dimension_scores = dict(legacy_scores)
    extended_overall = legacy_overall
    if metrics is not None:
        dimension_scores.update(_dimension_scores(phase6_map))
        dimension_scores.update(_dimension_scores(phase8_map))
        extended_overall = (
            sum(dimension_scores.values()) / len(dimension_scores) if dimension_scores else 0.0
        )

    return {
        "criterion_scores": scores,
        "dimension_scores": dimension_scores,
        # ``overall_score`` stays the legacy average so historical comparisons keep
        # meaning; the extended average is reported alongside, never in place of it.
        "overall_score": round(legacy_overall, 3),
        "legacy_overall_score": round(legacy_overall, 3),
        "extended_overall_score": round(extended_overall, 3),
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
        scoring = _score_case(case, scenario, metrics)

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
