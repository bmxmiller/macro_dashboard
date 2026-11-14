# MacroLens: roadmap and handoff

Everything a fresh session (or a fresh you) needs to pick the project back up. Last updated 2026-11-14. See also [CLAUDE.md](../CLAUDE.md) (rules, commands, agents, skills) and [AI_WORKFLOW.md](AI_WORKFLOW.md) (how it was built, incidents, lessons).

## 1. Where things stand
- **Live:** https://bmxmiller.github.io/macro_dashboard/ · **Repo:** `bmxmiller/macro_dashboard` (public). Always use the **bmxmiller** GitHub account.
- **Updates itself:** `update-data` runs weekdays 22:30 UTC and Saturdays 12:00 UTC (full rebuild). The bot pushes data with a deploy key, CI runs on that commit, and `deploy` publishes only if CI passes.
- **`main` is protected** (ruleset: PR + 3 green checks, no force-push or delete). The deploy key is the only bypass. Direct pushes are rejected.
- **Built:** 15 panels, 22 US + 10 UK indicators, 89 market rows, 13 news feeds, 7 CFTC markets, AI brief + rule-based macro regime. **260 pytest tests**, 10 Playwright e2e tests, ~4,500 lines of Python and ~2,000 of TypeScript.
- **AI chain** (`pipeline/registry/ai.yaml`): `gemini-3.5-flash-lite`, then Groq `gpt-oss-120b`, then `gpt-oss-20b`. `gemini-3.8-flash` was removed (it timed out and 503'd). The regime is computed by code and published every run; only the brief and the explainer need an LLM.
- **Secrets on GitHub:** `FRED_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `DATA_DEPLOY_KEY`. Local keys are in `.env` (gitignored).

## 2. Start here next session
```bash
cd Macro_Dashboard
git checkout main && git pull
./.venv/Scripts/python -m pytest -q                      # 260 tests (pyproject hides the summary line)
./.venv/Scripts/python -m pipeline.build --only markets  # one section (needs .env for FRED/LLM keys)
cd web && npm install && npm run dev                     # http://localhost:5173
npm run typecheck && npm run build && npm run test:e2e
```
Skills: `/add-metric`, `/new-panel`, `/ship-feature`. Agents (`.claude/agents/`): `finance-reviewer`, `data-verifier`, `prompt-redteamer`, `ui-reviewer`. Custom agent types load at session start; if one isn't found, spawn a `general-purpose` agent and tell it to read the `.md` and adopt it as its role.

## 3. Finishing and clean-up (do these first)
- [ ] **Rotate the three keys** (FRED, Groq, Gemini). They were pasted into a chat. Create new ones, update `.env` and the three GitHub secrets, delete the old ones.
- [ ] **Remove leftover worktrees and folders:** `git worktree remove ../Macro_Dashboard-wt/<ai-insights|data-panels|visual-qa>`, then delete `../Macro_Dashboard-wt/` (the old `frontend` folder was locked by Windows; restart VS Code first).
- [ ] **Delete merged branches:** local `agent/*`, `chore/readme-protection`, `feat/*`, `fix/*`; the same on `origin`. Then turn on *Settings → General → Automatically delete head branches*.
- [ ] **Close issue #9** (`prompt-redteamer` is built); confirm #8 closed with PR #15.
- [ ] **README:** drop "(rolling out)" from the AI row; re-check the panel/test counts; **retake `docs/images/` screenshots** (they predate the AI panels).
- [ ] **`docs/SETUP.md` is out of date:** it says deploy runs after every push and `update-data`; now deploy runs only after CI passes. Add the `DATA_DEPLOY_KEY` secret and how the key and the ruleset were created, plus the two AI secrets.
- [ ] **Look at the live site** in light, dark and mobile (the AI panels especially). This needs the Chrome tool; it was disconnected for most of the build, so the AI panels have never been viewed on the live site in an agent session.
- [ ] **Add a `LICENSE`** (decide: MIT?) and turn on GitHub secret scanning + push protection for the public repo.
- [ ] Pin the repo on your GitHub profile and add the live URL and topics to the repo About (the URL and topics are already set).

## 4. Biggest gap: panels from the original StableBread screenshots not built yet
The original brief was "all metrics included in the screenshots". Built: Index Snapshot, Economic Indicators, Sector, Fixed Income, Commodity and Currency performance, Economic Calendar, Four Quadrants (as *Macro Regime*). **Not built:**
- [ ] **Factors Performance** (momentum, quality, value, low vol, size…) and **Size vs Value**
- [ ] **Country ETF Performance** and **Global Equity Indexes**
- [ ] **Thematic Trends** (sparkline tiles: solar, uranium, lithium, space, cyber, genomics, defence…)
- [ ] **S&P 500 Heat Map** (treemap by market cap; needs constituents + market caps, the heaviest item)
- [ ] **Metrics Heat Map** (z-scores of the macro metrics; pairs well with issue #5, robust z-scores)
- [ ] **Commodities** and **Currencies** *price tables* (last price, units), separate from the performance panels
- [ ] **Growth × Policy** and **Credit × Duration** as charts (today they are rows inside the Macro Regime panel)

How: add the ticker groups to `pipeline/registry/universes.yaml` (most are ETFs that reuse the existing returns pipeline and `PerformancePanel`), then `/new-panel` for the rest. Do these as one parallel-agent round with `/ship-feature`.

## 5. Other wish-list items from the original plan
- [ ] **Thesis notebook:** save a thesis, snapshot the linked metrics at that date, show "then vs now" later (browser storage + export)
- [ ] **Watchlist** and **drag/resize layout** (react-grid-layout); today you can only show/hide panels
- [ ] **History chart for market rows** (click a ticker for its price history; today only economy/UK metrics have it)
- [ ] **Weekly long-form brief** (only a daily brief exists)
- [ ] Optional: Eurozone / Japan / China comparison table (not chosen in planning)

## 6. Backlog by area
**AI quality and safety**
- [ ] **#16: validator red-team.** About half of ~290 first-pass attack strings were accepted (some are true statements, so the exact figure needs re-verifying). Top numeric holes: label lost after a comma, `from X to Y` not an ordered pair, duplicate facts with no direction, horizon (week vs month) not compared, no aliases for sectors/tenors, number camouflage (decimal commas, odd spaces, ranges), exempt small integers. Plan: add the report's strings to `test_ai_validate_adversarial.py` first (they must fail), fix, re-run `prompt-redteamer`, and report honest before/after counts.
- [ ] Gemini `gemini-3.8-flash` re-test later (latency) or pick another model
- [ ] A weekly brief; per-cluster news grounding (restrict headline numbers to a cluster's own items)

**Data quality** · **#4** flag stale panels by data age · **#5** robust z-scores (COVID outliers) · **#6** re-bootstrap the UK 2Y gilt history (Sunday-dated points) · **#7** pin Python dependencies (yfinance breaks often) and add Dependabot.

**UI and accessibility** · **#14** (ui-reviewer): clipped panels with no cue, teal-on-white contrast ~2.4:1, light `--muted` below AA, 9px labels, undated subtitles, inconsistent date formats, empty grid areas, VIX tile coloured green when VIX rises, 22px tap targets. Re-run `ui-reviewer` after fixing.

**Infra and CI** · deploy waits for CI (done). Note: `ci` cancels superseded runs on the same branch, so a data commit pushed right after a merge cancels the merge commit's CI; the final commit's CI covers it. Consider `cancel-in-progress: false` for `main`. Cache Playwright browsers to speed CI.

**Agent tooling** · **#10** weekly scheduled audit (a cloud routine that runs `data-verifier` against the live site and opens an issue on any mismatch; uses your Claude plan, so it needs an explicit go-ahead). Ideas: a SessionStart hook that prints data freshness, open PRs and failing workflows; a `/release-notes` skill.

## 7. CV and portfolio
- [ ] Pick 4–5 bullet points and a 90-second walkthrough (what it is, the architecture, one incident, one review catch, what you would do next). Material is in `AI_WORKFLOW.md` and the README.
- [ ] A short GIF or video of the live dashboard for the README and LinkedIn (needs the Chrome tool).
- [ ] **Be honest about limits:** don't claim "0 bypasses" for the AI validator; the accurate story is that an agent red-teamed it, proved it weaker than the tests suggested, and the claim was corrected and logged.
- [ ] Interview stories already written down in `AI_WORKFLOW.md`: the FRED User-Agent stall, a leaked API key caught in review, gap-blind YoY, the validator passing a mislabelled ETF price, a protected `main` with a deploy-key bypass, resuming interrupted agents.

## 8. Gotchas and lessons (so you don't re-learn them)
- **Windows worktrees:** the harness's `isolation: "worktree"` fails (drive-letter case mismatch). Create worktrees by hand outside the repo: `git worktree add -b feat/x ../Macro_Dashboard-wt/x main`.
- **FRED:** needs the free API key; the keyless CSV endpoint throttles and stalls browser-like User-Agents. All HTTP goes through `pipeline/fetchers/http.py`; pass per-request `browser_headers()` only for hosts that need them (BoE, CNN, CNBC, Yahoo RSS).
- **Secrets:** `meta.json` is public. Errors are passed through `redact()` before being stored. Never print keys.
- **Gemini keys** may start with `AQ.` (not `AIza`); don't validate the prefix. Models listed by the API can still 404; test with a real call.
- **Interrupted agents:** check their worktree (`git log`, `git status`), resume with a message that says what is done; have them commit and push after each block.
- **Hooks:** the post-edit hook can show a transient failure between two consecutive edits; it clears when the second edit lands.
- **ONS** dates 3-month labour-survey data by the *middle* month; the pipeline uses the window's end month.
- **Browser tool:** if Claude in Chrome isn't visible, restart Claude Code and check `/mcp`.

## 9. Open decisions
1. Harden the AI validator now (#16) or build the missing panels first?
2. Create the weekly scheduled audit (#10)?
3. Add a `LICENSE`, and which?
4. Which missing panels first (section 4)?
