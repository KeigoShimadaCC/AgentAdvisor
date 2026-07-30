# Cursor CLI research and harness test findings

**Date:** 2026-07-30
**Scope:** Can Cursor CLI serve as the Phase 1 agent backend for this platform, and how should the orchestrator drive it?
**Method:** Local empirical tests on the installed CLI plus documentation research.

---

## 1. Environment

- Binary: `cursor-agent` (also `cursor`), installed at `~/.local/bin/`
- Version tested: `2026.07.23-e383d2b`
- Auth: browser login active (Pro tier); `CURSOR_API_KEY` / `--api-key` available for headless auth
- Note: docs increasingly refer to the binary as `agent`; auto-update is on by default

## 2. Empirical test results

All tests run 2026-07-30 on macOS (arm64), isolated temp directories.

| # | Test | Command shape | Result |
|---|---|---|---|
| 1 | Headless text run | `cursor-agent -p --trust --model composer-2.5 --output-format text "<prompt>"` | Exact requested string returned; 14s round trip |
| 2 | File-artifact round trip | agent reads `task.json`, writes `answer.json` per an output schema; `--output-format json` | Artifact written correctly and schema-conformant; 19s |
| 3 | JSON envelope | same as 2 | Envelope contains `type`, `subtype`, `is_error`, `duration_ms`, `result`, `session_id`, `request_id`, `usage` (input/output/cache tokens) |
| 4 | Concurrency | 3 parallel invocations, 3 model families (composer-2.5, gpt-5.2, cursor-grok-4.5-low), separate working dirs | All succeeded, no interference, 32s wall total |

Key measurements:

- **Per-invocation overhead is large:** a trivial no-context task consumed roughly 12k-24k input tokens (harness system prompt plus context assembly). Invocation count, not prompt size, will dominate usage.
- **Concurrency works** across separate working directories, which answers north star open question #1 positively at small scale (n=3). Re-test at higher parallelism before relying on it.

## 3. Model catalogue (as listed by `cursor-agent models` on this account)

- Anthropic: `claude-opus-5-*` (low/medium/high/xhigh/max, thinking and fast variants), `claude-opus-4-8-*`, `claude-fable-5-*` (marked NO ZDR)
- OpenAI: `gpt-5.6-sol-*`, `gpt-5.5-high*`, `gpt-5.3-codex-*` (low through xhigh, fast variants), `gpt-5.2`
- Cursor: `composer-2.5`, `composer-2.5-fast`, `cursor-grok-4.5-*` (low/medium/high, fast variants)
- Other: `kimi-k3-high`, `auto`

Director-vs-Challenger model-family diversity is fully achievable per invocation via `--model`.

## 4. Usage keypoints for this repo

1. **Validated invocation pattern:** `cursor-agent -p --trust --force --model <id> --output-format json --workspace <agent-dir> "<task prompt>"`. Parse the JSON envelope; validate the written artifact against our schema; retry or escalate on failure.
2. **No schema-constrained generation flag exists.** `--output-format json` structures the transport envelope, not the model output. Our "agent writes file, orchestrator validates deterministically" design is the correct and only robust pattern.
3. **Two usage pools:** "Cursor Models" (Composer, Grok) versus "Other Models" (Anthropic, OpenAI; consume included plan usage, then on-demand billing). Run high-volume worker roles on Cursor-pool models to preserve included usage for Director, Challenger, and Synthesizer.
4. **Context pickup:** the CLI reads `AGENTS.md` (including nested files, precedence by specificity), `.cursor/rules`, and `CLAUDE.md`. This is the delivery mechanism for role definitions (a role md becomes the `AGENTS.md` of that agent's workspace), but it also means the repo-root `AGENTS.md` could leak into runtime agents if the workspace root is wrong. Always set `--workspace` to the agent's isolated directory and verify non-leakage in the smoke test.
5. **Guardrails, not security boundaries:** permissions live in `~/.cursor/cli-config.json` (global) and `<project>/.cursor/cli.json` (`Read()`, `Write()`, `Shell()`, `WebFetch()`, `Mcp(server:tool)` tokens); sandbox policy in `.cursor/sandbox.json`. `.cursorignore` does not block terminal or MCP tools. Docs state these are guardrails only.
6. **Failure handling:** failures produce a non-zero exit code and stderr output; a well-formed JSON success object is not guaranteed on failure. Community threads report occasional `-p` hangs. The orchestrator must wrap every invocation in a hard timeout and treat unparseable output as failure.
7. **Stability:** the CLI is beta with high changelog churn, and the binary auto-updates by default. Record the CLI version in each case audit log and re-run the smoke test after any update. Flag semantics (`--trust`, `--force`, sandbox) have shifted during 2025-2026.
8. **Sessions:** `session_id` from the envelope enables `--resume <chatId>`, a cheap option for repair cycles (resume the Director's session instead of re-projecting full context). Worth a controlled experiment; default remains fresh invocations with projected context.
9. **Read-only modes exist:** `--mode plan` and `--mode ask` restrict to read-only behavior, potentially useful for the Auditor.
10. **MCP works headless** (`.cursor/mcp.json`, `--approve-mcps`), relevant later for research tooling.

## 5. Recommended approach

- The orchestrator invokes headless `cursor-agent` as a subprocess per role invocation, one isolated workspace each, with the JSON envelope (tokens, duration, session_id, CLI version) logged to the case audit log.
- Initial role-to-model mapping (config-driven; expect name churn):

| Role | Model | Why |
|---|---|---|
| Planner, Auditor | `composer-2.5` | cheap, fast, Cursor pool |
| Researchers | `cursor-grok-4.5-low` or `composer-2.5` | high volume, Cursor pool |
| Analyst | `gpt-5.3-codex` | coding strength |
| Director | `claude-opus-5-thinking-high` | strong synthesis |
| Challenger | `gpt-5.6-sol-high` | different family from Director |
| Synthesizer | `claude-opus-5-thinking-high` | strongest available |

- Phase 0 must include a **harness smoke-test script** codifying the four tests above plus an AGENTS.md leakage check, so any CLI update can be re-validated with one command.

## 6. Open items carried forward

- Concurrency behavior above n=3 parallel invocations
- Whether repo-root `AGENTS.md` leaks into agents whose `--workspace` is a subdirectory of the repo
- Whether `--resume` preserves enough context for cheap repair cycles without violating context-isolation principles
- Effective per-role permission profiles (`.cursor/cli.json`) and sandbox settings
- Actual included-usage consumption per full decision case (measure in Phase 3)

## 7. Sources

Official: cursor.com/docs/cli/{overview, installation, using, headless, mcp, changelog, reference/{parameters, output-format, authentication, permissions, configuration}}, cursor.com/docs/{models, models-and-pricing, rules, reference/ignore-file, reference/sandbox, agent/security}, cursor.com/pricing, cursor.com/blog/{cli, increased-agent-usage, agent-sandboxing}.

Community (non-official, lower confidence): Cursor forum threads on headless hangs, stream-json parsing, model list regressions, and concurrency requests.

Empirical: local tests described in Section 2, runnable versions to be codified in the Phase 0 smoke-test spec.
