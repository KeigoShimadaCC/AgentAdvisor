import json
from pathlib import Path

payload = {
    "count": 3,
    "label": "stable",
    "nested": {"x": 1.25, "y": [1, 2.5, "ok"]},
}

Path("results.yaml").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
