# MacroLens: agent guide

Self-updating macro dashboard. A Python pipeline writes static JSON, a React app renders it, and GitHub Actions + Pages hosts it. **Everything must stay free** (no paid APIs or data).

## Layout
- `pipeline/`: Python 3.13. Run from the repo root: `./.venv/Scripts/python -m pipeline.build [--only markets economy yield_curve calendar]`
  - `registry/metrics.yaml`: every economic metric (series, transform, About text, source URL). **Add metrics here, never hardcode them in code.**
  - `registry/universes.yaml`: every ticker group shown in market panels.
  - `fetchers/`: one module per source. All HTTP goes through `fetchers/http.py` (retries, plain UA; FRED stalls browser-like UAs).
  - `transforms/`: pure functions (returns, econ transforms). These must stay pure and unit-tested.
  - `schemas.py`: pydantic contracts for every JSON output. Change these together with `web/src/types.ts`.
  - `build.py`: orchestrator. Each section is isolated: a failure keeps the last good JSON and is recorded in `meta.json`.
- `web/`: React 19 + Vite + TS + Tailwind v4. `npm run dev`, `npm run typecheck`, `npm run build`.
  - Data: `useData<T>("markets")` loads `web/public/data/markets.json`.
  - Every panel uses the `<Panel>` shell (`src/components/Panel.tsx`) and is registered in `src/panels/registry.tsx`.
  - **Reference panel pattern:** `src/panels/PerformancePanel.tsx`.
  - Colours: CSS tokens only (`var(--ink)`, `--accent`, `--pos`/`--neg` diverging). No raw hex in components. Performance cells use `perfBg()` from `lib/format.ts`.

## Rules
- Every metric shown must have an About text (what / why / how_to_read) and a link to its official source.
- Show signed numbers (+/−) so colour is never the only cue.
- Secrets come only from env vars (`FRED_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`) or `.env` (gitignored). Never commit them or print them.
- Before finishing: `./.venv/Scripts/python -m pytest pipeline/tests -q` and `cd web && npm run typecheck`.
- Log notable agent work, failures and fixes in `docs/AI_WORKFLOW.md`.

## Workflow
- Feature work happens on branches (`feat/*`) and goes through a **pull request**. CI (pytest, typecheck, build, e2e) must be green. `deploy` only runs after `ci` passes on main.
- Custom agents in `.claude/agents/` (read-only reviewers; custom agent types load at session start, so if one isn't found, spawn a `general-purpose` agent and tell it to read the `.md` file and adopt it as its role):
  - `finance-reviewer`: numbers, units, economics and About-text accuracy on every PR
  - `data-verifier`: checks published data against official sources
  - `prompt-redteamer`: attacks the AI fact-checker (`pipeline/ai/validate.py`) with plausible false outputs
  - `ui-reviewer`: screenshots and code for accessibility, contrast and layout
- Project skills in `.claude/skills/`: `/add-metric` (a new indicator), `/new-panel` (a new panel end to end), `/ship-feature` (the whole plan → parallel agents → PRs → review → merge → verify workflow)
- GitHub: always use the **bmxmiller** account. `main` is protected (PR + green CI); the daily data bot pushes with a deploy key (`DATA_DEPLOY_KEY`), which is the only bypass.
- Windows note: the harness's `isolation: "worktree"` fails on this machine (drive-letter case), so parallel agents use manual worktrees in `../Macro_Dashboard-wt/<name>`.
