# AI-first workflow log

How this project was built with an AI coding agent (Claude Code). It records what was delegated, how the work was verified, and what went wrong.

## Principles
- **Spec first**: started in plan mode with a structured requirements interview. The plan was approved before any code was written.
- **Contracts before parallelism**: shared JSON schemas (`pipeline/schemas.py` ↔ `web/src/types.ts`), the `<Panel>` shell and one reference panel were built first, so parallel agents could work independently without colliding.
- **Isolation**: parallel subagents each work in their own git worktree on disjoint files, then the orchestrator merges and verifies.
- **Guardrails by harness, not trust**: hooks run tests and typecheck automatically. A separate reviewer agent audits merged code.
- **Verify in reality**: the pipeline runs against live APIs, and the UI is checked in a real browser.

## Log

### Session 1 (2026-11-13): planning + foundations
- Plan mode: 3 rounds of requirement questions (stack, AI features, data rules, scope). Plan approved.
- Built the metric registry (YAML as single source of truth, with About texts drafted by AI and reviewed), FRED/Yahoo/FOMC fetchers, return transforms, pydantic schemas and the build orchestrator.
- **Incident: FRED stalls.** The pipeline hung for minutes. Diagnosis: single `curl` calls were instant, but Python calls timed out. Isolated variables one at a time and found that FRED silently stalls requests with a browser-like User-Agent (and then rate-limits bulk keyless CSV downloads). Fix: honest UA, sequential keyless fallback, and the free FRED API key as the primary path. Lesson recorded in `CLAUDE.md` so future agents don't reintroduce it.
- Front-end foundations: design tokens (dark/light, user accent, diverging gain/loss palette with a colour-blind-safe option), `<Panel>` shell (About popover, PNG export, hide, stale badge) and a reference `PerformancePanel`.

### Session 1 (continued): parallel agents
**Orchestration.** After the shared contracts were committed, three background subagents ran in parallel, each in its own git worktree and branch, on disjoint files:

| Agent | Branch | Delivered | Notable problems it solved |
|---|---|---|---|
| Front-end | `agent/frontend` | Index Snapshot, Economic Indicators (ⓘ per metric), Yield Curve, Calendar, History modal with NBER recession shading | No FRED key, so it built a schema-validated synthetic fixture generator (never committed). The bundle hit 828 kB, so ECharts was tree-shaken and lazy-loaded (main bundle 86 kB gzipped). Charts read theme colours one frame late, which was fixed. |
| Pipeline | `agent/pipeline` | UK macro (BoE + ONS), CFTC COT positioning, CNN Fear & Greed + VIX term structure, RSS news (13 feeds), earnings calendar | Probed every endpoint: BoE/CNN/CNBC/Yahoo reject plain UAs while BLS rejects browser UAs, so headers are set per host. No BoE 2y gilt series exists, so it is derived from the BoE yield-curve spreadsheets with an incremental history cache. ONS GDP first estimates live in a different dataset, so both are fetched and the newer one wins. |
| Infra/tests | `agent/infra` | 50 offline pytest tests, CI, scheduled data-update workflow, Pages deploy, beginner setup guide | `workflow_run` chaining, because commits pushed with `GITHUB_TOKEN` don't trigger other workflows. Workflow inputs go through env vars to prevent shell injection. Validated with actionlint. |

**Incident: worktree isolation refused to start.** The harness rejected its own worktrees because of a Windows drive-letter case mismatch (`c:\` vs `C:/`). Workaround: created the worktrees manually with `git worktree add` and pointed each agent at its own absolute path. Same isolation, set up by hand.

**Guardrail in action.** While fixing a bug the pipeline agent flagged (weekly history labelled with future Sundays), the post-edit hook ran pytest between the code edit and the test edit and fed the failure back automatically. That shows a broken intermediate state is caught immediately.

**Merge and verify.** Merged in order (infra → frontend → pipeline) with no conflicts. Verified with 76/76 tests, typecheck + production build, a live pipeline run (7 sections OK) and a browser check of the merged dashboard. The browser check found one UX bug (a missing JSON file showed a raw parse error, because the SPA fallback serves index.html), which was fixed. An independent read-only reviewer agent then audited the merged code.

### Independent review → fixes
A read-only reviewer agent audited the merged code and reported 14 verified findings. Both high-severity issues were fixed the same session, each with a regression test (`pipeline/tests/test_review_fixes.py`):
- **Secret leak (high):** `requests` embeds the full URL, including `api_key`, in error text, which flowed into the public `meta.json`. Fix: a `redact()` helper and a logging filter. Only redacted errors are stored. The FRED calendar call now degrades instead of failing.
- **Gap-blind YoY (high):** `pct_change(12)` counted rows, not months. A single unpublished month (e.g. the Oct-2025 CPI during the shutdown) turned YoY into a 13-month change for a year. Fix: `asfreq("MS"/"QS")` re-inserts gaps.
- Also fixed: empty sections marked "ok" (markets/yield curve now fail and keep last good data), FX quote direction labelled, calendar time sort, `http(s)`-only news links, registry-loading tests in CI, and three factual corrections in About texts (Sahm 2024 false positive, CPI-U vs CPI-W indexation, VIX term-structure thresholds).

**Open follow-ups** (accepted, not yet done): stale-by-age detection in the UI; LFS period labels (Jun–Aug shown as Jul); re-bootstrap 2Y gilt history; "previous" for step series like policy rates; robust z-scores excluding the 2020 COVID outliers; pin Python deps and gate deploy on CI.

### Session 2 (2026-11-14): live FRED data + external validation
- FRED API key added locally (`.env`, gitignored). Economy, yield curve and the full release calendar were built live.
- **Cross-validated against an independent source** (the StableBread dashboard): CPI, core CPI, core PCE, NFP, unemployment, UMich, retail sales, debt/GDP and interest/GDP all match to the decimal (core CPI prev differs by rounding). The only difference is PPI, where we chose BLS *final demand* PPI (the headline series) and the reference uses a different PPI index. That is a choice of measure, documented rather than "fixed".
