import json
from pathlib import Path

payload = {
    "count": 4,
    "label": "changed",
    "nested": {"x": 2.0},
}

Path("results.yaml").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
