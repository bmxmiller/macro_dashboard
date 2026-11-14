---
name: ship-feature
description: Ship a feature on MacroLens the way this project works: plan, shared contracts, parallel agents in isolated worktrees, one pull request each, CI + code review + finance review, fixes relayed to the authoring agent, merge, then verify the live site. Use when the user asks to build something that touches more than one area (e.g. new panels plus new data, or any feature worth parallelising).
argument-hint: "<feature to build, e.g. 'positioning panel + COT history'>"
---

# Ship a feature: $ARGUMENTS

`main` is **protected**: changes only arrive through a pull request with green CI (pytest, typecheck + build, Playwright e2e). The data bot is the one exception (deploy key). Use the **bmxmiller** GitHub account for every `gh` and push action (check `gh auth status`).

## 1. Plan before code
- Enter plan mode. Ask the user the questions that change what you build, and don't guess. Write the plan to the plan file and get approval.
- Decide whether to parallelise. Split only when the pieces are independent and touch different files. If they are tightly coupled, do it yourself in one branch.

## 2. Contracts first (you, the orchestrator)
Before any agent starts, make the shared things exist and are committed to `main` via a PR:
- Data shapes: `pipeline/schemas.py` ↔ `web/src/types.ts` (the same fields).
- The panel pattern to copy (`web/src/panels/PerformancePanel.tsx`, the `<Panel>` shell, `useData`, `useStale`).
- **File ownership.** Give each agent a list of files it alone may edit. Append-only shared files (`types.ts`, `schemas.py`) are the only overlap, and you resolve those at merge. `web/src/panels/registry.tsx` has exactly one owner.

## 3. Worktrees (Windows workaround)
The harness's `isolation: "worktree"` fails on this machine (a drive-letter case mismatch), so create them by hand, outside the repo:
```bash
git worktree add -b feat/<name> ../Macro_Dashboard-wt/<name> main
```
Tell each agent its absolute worktree path and that it must never edit the main checkout.

## 4. Brief each agent (background agents, one message with all spawns)
Every brief includes: the goal; files it owns and files it must not touch; the patterns to read first (`CLAUDE.md`, the reference panel); the rules (CSS tokens only, signed numbers, an About text and a source link for every metric, no secrets printed); how to verify (`pytest`, `npm run typecheck`, `npm run build`, `npm run test:e2e`); **commit and push after each finished block** (so an interruption costs one block, not the whole job); open **no** PR (you do that); and a short final report: files, design choices, test results, what is unfinished, and a 3–5 sentence workflow-log entry.

The post-edit hook (`.claude/hooks/post_edit_check.py`) runs pytest/tsc after every edit and feeds failures back. A transient failure between two consecutive edits is normal.

## 5. Handle interruptions
If an agent dies (API error, stream stall), look at its worktree (`git log`, `git status`, `git diff --stat`), then resume it with `SendMessage` saying exactly what is done and what is left. Never restart it from scratch.

## 6. Pull request per branch
`gh pr create` with: what changed, why, how it was verified, and what is deliberately limited. End the PR description with the "🤖 Generated with Claude Code" line.

## 7. Review before merge (all of these, on every PR)
1. Wait for CI: `gh pr checks <n> --watch`.
2. `/code-review medium <n> --comment` for inline PR comments.
3. The custom agents in `.claude/agents/` as appropriate: `finance-reviewer` (numbers, units, About text, AI claims), `ui-reviewer` (screenshots, contrast, layout), `prompt-redteamer` (if `pipeline/ai/**` changed). Custom agents are loaded when the session starts, so if the agent type isn't found, spawn a `general-purpose` agent and tell it to read the `.md` file and adopt it exactly as its role.
4. Merge the findings into one prioritised list and send it to the authoring agent with `SendMessage`. Don't fix other agents' work yourself unless it's trivial.
5. Re-run the tests yourself before merging; don't trust an agent's summary.

## 8. Merge
`gh pr merge <n> --merge` once the checks are green and the state is CLEAN. Merge in dependency order; resolve shared-file conflicts, then re-check CI. After the merge: `git checkout main && git pull`.

## 9. Verify the live site
Push the change through the real pipeline: `gh workflow run update-data -f sections="..."`, then wait for `update-data` → `ci` → `deploy` (data commits are pushed with a deploy key, so they trigger CI; deploy runs only after CI passes). Then check what users see: the published `web/public/data/*.json` on https://bmxmiller.github.io/macro_dashboard/data/, the `data-verifier` agent against official sources, and, if the Chrome tools are connected, the real page in light, dark and mobile.

## 10. Leave a record
Append a dated entry to `docs/AI_WORKFLOW.md` (through a PR): what was delegated, what the reviews found, what went wrong and how it was fixed, and what is **not** verified. Be honest about limits. That file is the project's evidence of how it was built.
