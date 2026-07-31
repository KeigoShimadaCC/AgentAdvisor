from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = REPO_ROOT / "benchmarks" / "cases"
RUBRIC_PATH = REPO_ROOT / "benchmarks" / "rubric.yaml"

SCENARIO_REQUIRED_KEYS = {
    "prompt",
    "slug",
    "budget_profile",
    "framing_approval",
    "notes",
}


def _load_yaml(path: Path) -> dict:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} must contain a YAML mapping"
    return loaded


def test_all_five_scenarios_parse_and_have_required_fields() -> None:
    scenario_paths = sorted(SCENARIOS_DIR.glob("scenario-*.yaml"))
    assert len(scenario_paths) == 5

    for path in scenario_paths:
        scenario = _load_yaml(path)
        for key in SCENARIO_REQUIRED_KEYS:
            assert key in scenario, f"{path} missing '{key}'"
        framing_approval = scenario["framing_approval"]
        assert isinstance(framing_approval, dict), f"{path} framing_approval must be mapping"


def test_rubric_parses_and_dimension_weights_positive() -> None:
    rubric = _load_yaml(RUBRIC_PATH)
    dimensions = rubric.get("dimensions")
    assert isinstance(dimensions, dict)
    assert dimensions

    for name, payload in dimensions.items():
        assert isinstance(payload, dict), f"dimension {name} payload must be mapping"
        weight = payload.get("weight")
        assert isinstance(weight, (float, int)), f"dimension {name} weight must be numeric"
        assert weight > 0, f"dimension {name} weight must be positive"


def test_rubric_criterion_ids_are_unique() -> None:
    rubric = _load_yaml(RUBRIC_PATH)
    dimensions = rubric["dimensions"]
    assert isinstance(dimensions, dict)

    ids: list[str] = []
    for payload in dimensions.values():
        assert isinstance(payload, dict)
        criteria = payload.get("criteria")
        assert isinstance(criteria, list)
        for criterion in criteria:
            assert isinstance(criterion, dict)
            criterion_id = criterion.get("id")
            assert isinstance(criterion_id, str)
            ids.append(criterion_id)

    assert len(ids) == len(set(ids)), "criterion IDs must be unique"
