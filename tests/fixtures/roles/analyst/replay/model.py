import json
from pathlib import Path

results = {
    "expected_values_by_alternative": {
        "invest_now": 115.0,
        "wait": 101.0,
    },
    "scenarios": {
        "bull": {"interval": [0.25, 0.35]},
        "base": {"interval": [0.35, 0.45]},
        "bear": {"interval": [0.15, 0.25]},
        "failure": {"interval": [0.08, 0.15]},
    },
    "sensitivity_table": [
        {
            "parameter": "bull_payoff",
            "parameter_value": 120.0,
            "preferred_alternative": "wait",
            "resulting_expected_values": {"invest_now": 96.0, "wait": 99.0},
        },
        {
            "parameter": "bull_payoff",
            "parameter_value": 170.0,
            "preferred_alternative": "invest_now",
            "resulting_expected_values": {"invest_now": 120.0, "wait": 101.0},
        },
    ],
    "break_even_thresholds": [
        {
            "parameter": "bull_payoff",
            "threshold_value": 132.0,
            "favored_alternative_below": "wait",
            "favored_alternative_above": "invest_now",
        }
    ],
}

Path("results.yaml").write_text(
    json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
