# AgentAdvisor Frontend

Local web UI for the decision-intelligence platform (SPEC-033+).

## Quick start

```bash
# Terminal 1: start the backend
uv run advisor ui --cases-root tests/fixtures/cases

# Terminal 2: start the dev server (proxies /api to :8765)
cd frontend && npm install && npm run dev
```

Open http://localhost:5173

## Replay mode

Replays a fixture case's audit events at scaled timing without spending model tokens:

```bash
uv run advisor ui --replay tests/fixtures/cases/case-001-fixture-001 --speed 60
```

## Scripts

| Script | Description |
|--------|-------------|
| `npm run dev` | Vite dev server with proxy to backend |
| `npm run build` | Production build to `dist/` |
| `npm run typecheck` | TypeScript type check (`tsc --noEmit`) |
| `npm test` | Vitest unit tests |
| `npm run generate:types` | Regenerate TS types from JSON schemas |
| `npm run check:clean` | Fail if generated types have drifted from `schemas/` |

`make frontend-check` runs the typecheck, the drift check, and the tests together.
There is no ESLint setup yet; this table used to list one that did not exist.

## Architecture

- `src/generated/` — TypeScript types generated from `schemas/*.schema.json` (do not edit)
- `src/api/client.ts` — typed REST client
- `src/api/sse.ts` — SSE client with cursor resume
- `src/pages/` — route screens (library, case detail)
- `src/App.tsx` — root component with routes

The FastAPI backend serves `dist/` when present (production mode).
