"""Domain specialist skill packs.

Selection is deterministic keyword scoring done by the orchestrator, never by an agent,
and never recursive: a pack is markdown appended to a role's instructions, not another
agent. Verification-facing roles are excluded from packs so domain framing cannot bias
the check on the work.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REGISTRY_PATH = Path(__file__).resolve().parents[1] / "cursor" / "skills" / "registry.yaml"
MAX_PACKS_PER_CASE = 2
MIN_PACK_SCORE = 2
_WORD_RE = re.compile(r"[a-z][a-z0-9-]+")


@dataclass(frozen=True, slots=True)
class SkillPack:
    pack_id: str
    title: str
    path: Path
    roles: frozenset[str]
    keywords: tuple[str, ...]

    def body(self) -> str:
        return self.path.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def load_registry(registry_path: str | None = None) -> tuple[SkillPack, ...]:
    path = Path(registry_path) if registry_path else REGISTRY_PATH
    if not path.exists():
        return tuple()
    loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root = path.resolve().parents[2]
    packs: list[SkillPack] = []
    for entry in loaded.get("packs", []):
        packs.append(
            SkillPack(
                pack_id=str(entry["id"]),
                title=str(entry["title"]),
                path=root / str(entry["path"]),
                roles=frozenset(str(role) for role in entry.get("roles", [])),
                keywords=tuple(str(word).lower() for word in entry.get("keywords", [])),
            )
        )
    return tuple(packs)


def score_pack(pack: SkillPack, text: str) -> int:
    lowered = text.lower()
    tokens = set(_WORD_RE.findall(lowered))
    score = 0
    for keyword in pack.keywords:
        if " " in keyword:
            score += 2 if keyword in lowered else 0
        elif keyword in tokens:
            score += 1
    return score


def select_packs(text: str, *, limit: int = MAX_PACKS_PER_CASE) -> list[SkillPack]:
    """Pick the highest-scoring packs for a decision question. May return nothing."""
    scored = [(score_pack(pack, text), pack) for pack in load_registry()]
    qualifying = sorted(
        (pair for pair in scored if pair[0] >= MIN_PACK_SCORE),
        key=lambda pair: (-pair[0], pair[1].pack_id),
    )
    return [pack for _, pack in qualifying[:limit]]


def packs_for_role(packs: list[SkillPack], role: str) -> list[SkillPack]:
    return [pack for pack in packs if role in pack.roles]


def render_pack_section(packs: list[SkillPack]) -> str:
    if not packs:
        return ""
    blocks = [
        "\n\n---\n\n# Domain specialist guidance\n\n"
        "The following pack(s) were selected by the orchestrator based on the decision "
        "question. They describe what competent analysis in this domain looks like. They "
        "do not tell you what to conclude, and they never override your role instructions "
        "or the output schema.\n"
    ]
    for pack in packs:
        blocks.append(f"\n<!-- skill-pack: {pack.pack_id} -->\n\n{pack.body().rstrip()}\n")
    return "".join(blocks)
