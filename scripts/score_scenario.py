#!/usr/bin/env python3
"""Score a case against benchmark rubric criteria."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

OBJECTIVE_CRITERIA = {
    "dc-1",
    "dc-2",
    "eq-1",
    "eq-2",
    "eq-3",
    "aq-1",
    "aq-3",
    "ar-1",
    "tr-1",
    "tr-2",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Expected a YAML mapping at {path}")
    return loaded


def _load_yaml_records(directory: Path) -> list[dict[str, Any]]:
    if not directory.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.yaml")):
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            out.append(loaded)
    return out


def _find_final_recommendation_md(case_dir: Path) -> Path:
    candidates = [
        case_dir / "outputs" / "final_recommendation.md",
        case_dir / "final_recommendation.md",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _has_non_empty_string_list(value: Any) -> bool:
    if not isinstance(value, list):
        return False
    return any(isinstance(item, str) and item.strip() for item in value)


def _criteria_index(rubric: dict[str, Any]) -> dict[str, dict[str, Any]]:
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, dict):
        return {}
    index: dict[str, dict[str, Any]] = {}
    for dimension_name, dimension_payload in dimensions.items():
        if not isinstance(dimension_payload, dict):
            continue
        criteria = dimension_payload.get("criteria")
        if not isinstance(criteria, list):
            continue
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            criterion_id = criterion.get("id")
            if isinstance(criterion_id, str):
                index[criterion_id] = {
                    "dimension": dimension_name,
                    "name": criterion.get("name", ""),
                    "description": criterion.get("description", ""),
                }
    return index


def _score_objective_criteria(case_dir: Path, final_md_text: str) -> dict[str, dict[str, Any]]:
    decision_spec_path = case_dir / "shared" / "decision_spec.yaml"
    intake_path = case_dir / "shared" / "intake_record.yaml"
    final_yaml_path = case_dir / "outputs" / "final_recommendation.yaml"
    evidence_records = _load_yaml_records(case_dir / "shared" / "evidence")
    objection_records = _load_yaml_records(case_dir / "shared" / "objections")
    analysis_results = _load_yaml_records(case_dir / "analysis")

    decision_spec = _load_yaml(decision_spec_path) if decision_spec_path.exists() else {}

    alternatives = decision_spec.get("alternatives")
    alt_count = len(alternatives) if isinstance(alternatives, list) else 0
    if alt_count >= 5:
        dc1_score = 2
    elif alt_count >= 3:
        dc1_score = 1
    else:
        dc1_score = 0

    has_objectives = _has_non_empty_string_list(decision_spec.get("objectives"))
    has_constraints = _has_non_empty_string_list(decision_spec.get("constraints"))
    if has_objectives and has_constraints:
        dc2_score = 2
    elif has_objectives or has_constraints:
        dc2_score = 1
    else:
        dc2_score = 0

    authoritative_keywords = ("regulatory", "filing", "official", "primary")
    authoritative_count = 0
    with_limitations_count = 0
    for record in evidence_records:
        source_type = str(record.get("source_type", "")).lower()
        if any(keyword in source_type for keyword in authoritative_keywords):
            authoritative_count += 1
        limitations = record.get("limitations")
        if _has_non_empty_string_list(limitations):
            with_limitations_count += 1
    if authoritative_count >= 2:
        eq1_score = 2
    elif authoritative_count == 1:
        eq1_score = 1
    else:
        eq1_score = 0

    inline_evidence_refs = re.findall(r"\[E-\d+\]", final_md_text)
    eq2_score = 2 if inline_evidence_refs else 0

    if not evidence_records:
        eq3_score = 0
    elif with_limitations_count == len(evidence_records):
        eq3_score = 2
    elif with_limitations_count > 0:
        eq3_score = 1
    else:
        eq3_score = 0

    sensitivity_tables: list[list[Any]] = []
    for result in analysis_results:
        table = result.get("sensitivity_table")
        if isinstance(table, list):
            sensitivity_tables.append(table)
    if sensitivity_tables:
        aq1_score = 2
        max_sensitivity_rows = max(len(table) for table in sensitivity_tables)
    elif analysis_results:
        aq1_score = 1
        max_sensitivity_rows = 0
    else:
        aq1_score = 0
        max_sensitivity_rows = 0

    if max_sensitivity_rows >= 3:
        aq3_score = 2
    elif max_sensitivity_rows > 0:
        aq3_score = 1
    else:
        aq3_score = 0

    objection_count = len(objection_records)
    if objection_count >= 3:
        ar1_score = 2
    elif objection_count >= 1:
        ar1_score = 1
    else:
        ar1_score = 0

    has_e_refs = bool(re.search(r"\[E-\d+\]", final_md_text))
    has_a_refs = bool(re.search(r"\[A-\d+\]", final_md_text))
    if has_e_refs and has_a_refs:
        tr1_score = 2
    elif has_e_refs or has_a_refs:
        tr1_score = 1
    else:
        tr1_score = 0

    chain_presence = {
        "intake_record": intake_path.exists(),
        "decision_spec": decision_spec_path.exists(),
        "evidence": len(evidence_records) > 0,
        "analysis": len(analysis_results) > 0,
        "objections": len(objection_records) > 0,
        "final_recommendation": final_yaml_path.exists() or bool(final_md_text.strip()),
    }
    present_count = sum(1 for present in chain_presence.values() if present)
    if present_count == len(chain_presence):
        tr2_score = 2
    elif present_count >= 4:
        tr2_score = 1
    else:
        tr2_score = 0

    return {
        "dc-1": {
            "score": dc1_score,
            "max_score": 2,
            "evidence": {"alternative_count": alt_count},
        },
        "dc-2": {
            "score": dc2_score,
            "max_score": 2,
            "evidence": {
                "has_objectives": has_objectives,
                "has_constraints": has_constraints,
            },
        },
        "eq-1": {
            "score": eq1_score,
            "max_score": 2,
            "evidence": {
                "authoritative_evidence_count": authoritative_count,
                "total_evidence_records": len(evidence_records),
            },
        },
        "eq-2": {
            "score": eq2_score,
            "max_score": 2,
            "evidence": {"inline_evidence_citation_count": len(inline_evidence_refs)},
        },
        "eq-3": {
            "score": eq3_score,
            "max_score": 2,
            "evidence": {
                "records_with_limitations": with_limitations_count,
                "total_evidence_records": len(evidence_records),
            },
        },
        "aq-1": {
            "score": aq1_score,
            "max_score": 2,
            "evidence": {
                "analysis_result_count": len(analysis_results),
                "has_sensitivity_table": bool(sensitivity_tables),
            },
        },
        "aq-3": {
            "score": aq3_score,
            "max_score": 2,
            "evidence": {"max_sensitivity_rows": max_sensitivity_rows},
        },
        "ar-1": {
            "score": ar1_score,
            "max_score": 2,
            "evidence": {"objection_record_count": objection_count},
        },
        "tr-1": {
            "score": tr1_score,
            "max_score": 2,
            "evidence": {
                "has_evidence_references": has_e_refs,
                "has_assumption_references": has_a_refs,
            },
        },
        "tr-2": {
            "score": tr2_score,
            "max_score": 2,
            "evidence": {"artifact_chain_presence": chain_presence},
        },
    }


def _build_subjective_template(
    rubric: dict[str, Any], criteria_meta: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, dict):
        return []
    template: list[dict[str, Any]] = []
    for _, dimension_payload in dimensions.items():
        if not isinstance(dimension_payload, dict):
            continue
        criteria = dimension_payload.get("criteria")
        if not isinstance(criteria, list):
            continue
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            criterion_id = criterion.get("id")
            if not isinstance(criterion_id, str):
                continue
            if criterion_id in OBJECTIVE_CRITERIA:
                continue
            meta = criteria_meta.get(criterion_id, {})
            template.append(
                {
                    "id": criterion_id,
                    "dimension": meta.get("dimension", ""),
                    "name": meta.get("name", ""),
                    "description": meta.get("description", ""),
                    "score": None,
                    "notes": "",
                }
            )
    return template


def _objective_summary(
    rubric: dict[str, Any],
    objective_scores: dict[str, dict[str, Any]],
    criteria_meta: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    dimensions = rubric.get("dimensions")
    if not isinstance(dimensions, dict):
        return {}
    per_dimension: dict[str, dict[str, Any]] = {}
    for dimension_name, dimension_payload in dimensions.items():
        if not isinstance(dimension_payload, dict):
            continue
        criteria = dimension_payload.get("criteria")
        if not isinstance(criteria, list):
            continue
        scored_ids: list[str] = []
        total = 0.0
        for criterion in criteria:
            if not isinstance(criterion, dict):
                continue
            criterion_id = criterion.get("id")
            if not isinstance(criterion_id, str):
                continue
            if criterion_id not in objective_scores:
                continue
            total += float(objective_scores[criterion_id]["score"])
            scored_ids.append(criterion_id)
        if not scored_ids:
            continue
        per_dimension[dimension_name] = {
            "objective_criteria_scored": scored_ids,
            "objective_average_score": round(total / len(scored_ids), 3),
            "objective_total_score": total,
            "objective_max_score": float(2 * len(scored_ids)),
        }

    overall_total = sum(float(v["score"]) for v in objective_scores.values())
    overall_max = float(2 * len(objective_scores)) if objective_scores else 0.0
    return {
        "per_dimension": per_dimension,
        "objective_overall_total": overall_total,
        "objective_overall_max": overall_max,
        "objective_overall_average": round(overall_total / len(objective_scores), 3)
        if objective_scores
        else 0.0,
        "objective_only_note": (
            "Subjective criteria still require human scoring before a complete "
            "rubric score is final."
        ),
        "criteria_descriptions": {
            criterion_id: criteria_meta.get(criterion_id, {})
            for criterion_id in sorted(objective_scores.keys())
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Score a benchmark scenario case directory.")
    parser.add_argument("case_dir", type=Path, help="Path to case directory (case-XXX-slug).")
    parser.add_argument("scenario_yaml", type=Path, help="Path to benchmark scenario YAML file.")
    parser.add_argument(
        "--rubric",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "benchmarks" / "rubric.yaml",
        help="Path to rubric YAML file.",
    )
    parser.add_argument("--output", type=Path, help="Optional output path for score YAML.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    case_dir = args.case_dir.resolve()
    scenario = _load_yaml(args.scenario_yaml.resolve())
    rubric = _load_yaml(args.rubric.resolve())

    final_md_path = _find_final_recommendation_md(case_dir)
    final_md_text = final_md_path.read_text(encoding="utf-8") if final_md_path.exists() else ""

    criteria_meta = _criteria_index(rubric)
    objective_scores = _score_objective_criteria(case_dir, final_md_text)
    subjective_template = _build_subjective_template(rubric, criteria_meta)
    summary = _objective_summary(rubric, objective_scores, criteria_meta)

    output_payload: dict[str, Any] = {
        "scenario": {
            "id": scenario.get("id", ""),
            "title": scenario.get("title", ""),
            "slug": scenario.get("slug", ""),
            "path": str(args.scenario_yaml.resolve()),
        },
        "case_dir": str(case_dir),
        "rubric_path": str(args.rubric.resolve()),
        "objective_scores": objective_scores,
        "objective_summary": summary,
        "subjective_template": subjective_template,
    }

    dumped = yaml.safe_dump(output_payload, sort_keys=False, allow_unicode=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(dumped, encoding="utf-8")
    else:
        print(dumped, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
