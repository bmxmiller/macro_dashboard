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
