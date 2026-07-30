# AGENTS.md leakage experiments for `cursor-agent`

**Date:** 2026-07-31  
**Scope:** Empirically determine ancestor `AGENTS.md` discovery behavior and cheapest reliable mitigation for runtime agent workspace isolation.

---

## Short summary

`cursor-agent` loads `AGENTS.md` from ancestor directories of the workspace path, not just the nearest file.  
A local workspace `AGENTS.md` does **not** suppress ancestor `AGENTS.md`; both are visible.  
Neither a child `.git` boundary nor explicit `--workspace` prevents ancestor leakage when the workspace remains under that ancestor tree; placing workspaces outside the repo tree is clean.

## Method

- All probes used `cursor-agent` `2026.07.23-e383d2b` with:
  - `--trust --force --model composer-2.5 --output-format json`
  - hard timeout: 120s per invocation
- Prompt template (machine-checkable):
  - `Reply with exactly the word FOUND if the string <SENTINEL> appears anywhere in your instructions or context, otherwise reply with exactly the word ABSENT. Reply with one word and nothing else.`
- Temp directories only (`/tmp` / OS temp); no `AGENTS.md` files created under `/Users/keigoshimada/Documents/AgentAdvisor`.

## Results

| Experiment | Setup | Sentinel | Raw answer | Verdict |
|---|---|---|---|---|
| E1 | `parent/AGENTS.md=S1`; workspace `parent/child`; no child `AGENTS.md` | `S1_DJAL8E8CNV` | `FOUND` | Leak confirmed |
| E2a | `parent/AGENTS.md=S1` and `child/AGENTS.md=S2`; workspace `child`; probe S1 | `S1_DJAL8E8CNV` | `FOUND` | Ancestor still visible |
| E2b | Same as E2a; probe S2 | `S2_HW2HJFQFG0` | `FOUND` | Local file visible too |
| E3 | `grandparent/AGENTS.md=S3`; workspace `grandparent/a/b`; no intermediate `AGENTS.md` | `S3_L0MK5323U4` | `FOUND` | Walk crosses >1 level |
| E4 | `parent/AGENTS.md=S4`; workspace `parent/child`; child contains initialized `.git` repo | `S4_FES76DYV57` | `FOUND` | `.git` does not stop walk |
| E5 (help/settings scan) | Checked `cursor-agent --help` and `~/.cursor/cli-config.json` for disable switch/key | N/A | No documented disable flag/env/key found for ancestor `AGENTS.md` discovery | No direct switch found |
| E5 (plausible flag test) | `parent/AGENTS.md=S5`; invoke from `/tmp` with `--workspace parent/child` | `S5_H0A1J6Y55Z` | `FOUND` | Explicit `--workspace` alone does not mitigate |
| E6 | Workspace in temp path outside repo tree; verified no ancestor `AGENTS.md` up to `/` | `S6_I1U1MC8T5W` | `ABSENT` | Clean baseline |

## Inferred discovery rule

Observed rule from E1-E4/E5/E6:

1. Instruction discovery follows the **workspace directory ancestry upward**.
2. Discovery includes ancestor `AGENTS.md` files at multiple levels (not only nearest).
3. A local `AGENTS.md` is **additive**, not suppressive.
4. A nested `.git` boundary does not terminate ancestor discovery.
5. `--workspace <path>` changes which path is searched, but does not disable upward discovery for that path.

## Mitigation recommendations (ranked)

1. **Top recommendation (reliable + simple): place runtime agent workspaces outside the repository tree.**  
   Example: `~/.local/share/agentadvisor/cases/<case-id>/agents/<role>--<task-id>/` (or `/tmp`-based case roots), each with role-specific `AGENTS.md`.
   - Pros: empirically clean (E6), no dependence on undocumented flags.
   - Cons: requires moving/copying projected inputs/artifacts between repo and runtime roots.

2. **If workspaces must stay inside the repo tree, safety requires removing/neutralizing ancestor `AGENTS.md` effects at the source.**  
   Based on E2/E4, local child files and `.git` boundaries are insufficient.
   - Practical implication: current layout `cases/<case-id>/agents/...` under this repo is **not safe** while root `AGENTS.md` exists and applies.

3. **Do not rely on hidden config/flag mitigation for now.**  
   Help/settings inspection found no documented `AGENTS.md`-discovery disable switch, and `--workspace` did not help when path remained under an ancestor with `AGENTS.md`.

## Direct answer to architecture choice

- **Should runtime case workspaces live inside this repo at `cases/<case-id>/agents/...`?**  
  **No**, not under current behavior.
- **If inside, what makes that safe?**  
  Only eliminating ancestor `AGENTS.md` influence (which local overrides and `.git` do not accomplish in these tests); absent a proven official disable control, this is not currently reliable.
