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

### Session 3 (2026-11-14): AI insights (agent B) and its review
- **Design: code decides, the LLM narrates.** A `regime` section (code only, no key) publishes three lenses to `regime.json`: a Growth × Inflation momentum quadrant (Investment-Clock style), Growth × Policy and Credit × Duration. The `insights` section then asks a free LLM (Gemini, Groq as fallback) for a brief, news clusters and an explainer, and an automatic fact check gates every answer.
- **Incident: model availability differs from the docs.** Live calls found `llama-3.3-70b-versatile` returned 404 on this Groq account, and `gemini-2.5-flash` was still listed by the models API but returned 404 "no longer available to new users". Models are now pinned in `ai.yaml` (Groq `openai/gpt-oss-120b`, Gemini `gemini-3.8-flash`). Keys in the new "AQ." format are masked by redacting the env-var values themselves.
- **Incident: a fact-checked answer was still wrong.** The first validator only checked that each number appeared somewhere in the digest. A Groq answer passed it while quoting ETF prices (SPY, DIA) as index levels, and the PR review produced 25 adversarial strings, 22 of which slipped through. The validator was rebuilt on explicit facts and now checks value at the data's precision, unit, sign/direction verb and the metric named before each number, plus advice words and regime names: 0/25 slip through, with no false rejections on 23 correct statements.
- **Review fixes (finance reviewer):** quadrant names that no longer clash with the Investment Clock, a flat state shown as a boundary, GDP momentum instead of level vs trend, staleness cut-offs, a Fed funds midpoint, duration-matched credit pairs, code-authored tendencies citing Greetham & Hartnett (2004), and source links on both AI panels.

### Session 4 (2026-11-14): PR workflow, protected `main`, and reviewing the first live AI output
**Process.** Three agents ran in parallel in manual worktrees, each ending in a pull request: Playwright e2e (PR #1), the five missing data panels (PR #2) and AI insights (PR #3). Each PR got CI, `/code-review` (inline PR comments) and the custom `finance-reviewer` agent. Findings went back to the authoring agent with `SendMessage` and were fixed before merge. PR #2 needed 16 fixes and PR #3 a validator rebuild.

**Verifying agent reports.** I re-ran the adversarial and full test suites myself before merging PR #3 instead of trusting the agent's summary. Both passed.

**Protected `main` and the data bot.** A ruleset now requires a PR and three green checks (pytest, typecheck + build, Playwright), and blocks force-push and deletion. A direct push was tested and rejected (GH013). The daily job pushes data to `main`, and personal repos can't exempt the Actions bot, so the job checks out with a write **deploy key** (repo-only SSH key; the private half is a secret and no local copy exists), the only bypass in the ruleset. A side effect that turned out useful: deploy-key pushes, unlike `GITHUB_TOKEN` pushes, trigger workflows, so **every data commit now runs the full CI suite, including browser tests, before `deploy` publishes it**. `deploy` now runs only after `ci` passes and builds exactly the commit that passed. The whole chain (bot push → CI → deploy) was exercised live.

**Backlog and docs.** Labels and 7 issues (#4–#10) record the review follow-ups and the agent-tooling ideas, and the README was merged through the new PR flow.

**Agent resilience.** Agent B was interrupted twice, by an API/DNS error and by a stream stall. It was resumed with an audit of what its worktree already held, and from then on committed and pushed after each priority block, so an interruption could cost at most one block.

**Reviewing the first live brief.** All numbers matched the data, but reading it found three problems the checks hadn't:
1. **A leaked internal key:** "...to a level_pct of 5.15". Fix: a validator check that rejects any snake_case identifier in AI text, and prompt rules for plain English. The new rule was run against the published file to confirm it flags that sentence.
2. **A cause stated as fact:** the headline said "chip deficits", which was not in the data. Prompt rule added (state what moved; attribute any reason to a headline). **This is a prompt instruction, not code-enforced:** a plausible invented cause can't be detected automatically, which is why the panel keeps its "AI-generated" label.
3. **Clumsy phrasing:** addressed by the same prompt change.

**Reading the CI logs paid off twice.**
- `gemini-3.8-flash` never answered: two 150 s read timeouts and then an HTTP 503 (about 5.5 minutes per run), while `gemini-3.5-flash-lite` answers in 2–3 s. The slow model was removed from the chain (reason recorded in `ai.yaml`) and the timeout cut to 60 s. This is based on one run's logs plus one isolated test call, so re-adding it later is cheap if it improves.
- The validator wrongly rejected a correct sentence: "US Dollar Index" had no alias, so the number was blamed on the nearest known metric (the 10Y yield). The retry-with-feedback loop masked it. Added the alias and positive and negative tests.
- A test that read the production model list broke when the list changed, so the fixture now pins its own chain.

**Not verified.** The browser tool disconnected and could not be reconnected from the agent side. The published data files were checked, but the AI panels have not been viewed on the live site in this session. The e2e suite checks that they render without errors.

**Red-teaming the validator (the `prompt-redteamer` agent's first run).** The earlier "22/25 → 0/25" figure only covered the 25 strings the validator had been built around. A separate read-only agent then wrote about 520 plausible wrong outputs against the real digest. Roughly half of the first-pass strings were accepted (some of those turned out to be true statements, so the exact bypass count needs re-verifying). The main numeric holes: a label is forgotten after a comma or parenthesis ("Core CPI, now at 3.7%, rose"), "from X to Y" is not checked as an ordered pair, a duplicate fact with no direction disables the rose/fell check, the horizon (week vs month) is never compared, sectors and most tenors have no alias, and odd number formatting (decimal commas, non-breaking spaces, ranges) hides numbers from the extractor. Advice wording ("poised to rally") and invented causes are not covered at all, and the latter cannot be, in principle, without a world model. It also found 2 false rejections in 50 natural sentences. **Consequence:** the README claim was corrected from a bare "0/25" to "a safety net, not a guarantee", and everything is tracked in issue #16. The lesson for the log: a test suite built from the attacks you already know tells you little about the attacks you don't.

### Session 5 (2026-11-14): S&P 500 heat map (`feat/sp500-heatmap`)
**What.** A new `sp500` pipeline section (503 constituents, prices in chunks of 100, share counts cached and refreshed on the Saturday run) and a treemap panel: area = market cap, grouped by GICS sector, colour = price return for the global period. No new dependency: ECharts' treemap series, registered in the existing lazy chunk.

**Caught by tests and screenshots, not by reading code.**
1. **YAML turned the ticker `ON` (ON Semiconductor) into the boolean `True`.** A registry test (every ticker is a string, no dots, no duplicates) failed on it; all tickers are now quoted. Worth remembering for any hand-edited ticker list.
2. **ECharts treemap quirks.** Sector headers did not render until I found that `levels[0]` is the invisible root (sectors are `levels[1]`) and that the header inherited my leaf label formatter, which returned an empty string for non-company nodes.
3. **Clipped labels read as wrong numbers.** Small rectangles showed "+1." or "−50" for real values like +1.3%. Labels now only draw when the text fits the rectangle's estimated width, otherwise the cell shows a ticker or nothing. The tooltip still carries every number.
4. **Canvas can't read `color-mix()` or CSS variables**, so `perfColor()` in `lib/format.ts` reproduces the `perfBg()` scale as a concrete `rgb()` (sRGB mix vs the table's oklab mix: near-identical, same saturation scale).

**Honest limits.** Returns are price returns (no dividends). Market cap uses Yahoo's latest share count, so it can lag buybacks. The constituent list is a Wikipedia snapshot, not an official feed. Colour is not the only cue (signed % labels, tooltip, and a leaders/laggards line), but the label-fit test is an estimate and was only checked visually at 1500px and 390px.

**Verification.** 260+ pytest tests, `tsc`, 10/10 Playwright tests, plus a live `pipeline.build --only sp500`: 503 rows, 0 failed, 103 KB. Spot-check of caps against Yahoo and the `finance-reviewer` / `ui-reviewer` passes are still to do before merge.

**Review round on PR #18 (finance-reviewer, data-verifier, ui-reviewer, run in parallel).** All three found real problems the tests had not:
1. **Alphabet counted twice (finance-reviewer and data-verifier, independently).** Yahoo returns the company-wide share count for every class ticker, so GOOGL and GOOG each got the full 12.29B shares (about $7.2T of Alphabet on the map, ~5% of the total). News Corp had the same fault. My registry comment even claimed "each class has its own market cap", which was false. Fix: one row per company (GOOG, FOX, NWS folded into the first class) and a registry test that fails if a second class comes back.
2. **Stale share counts after a split.** Shares refresh weekly, so a split would have shrunk a company ~10x until Saturday. Fix: closes are split-adjusted, so a mismatch between the price we published for the previous day and that day's close in the new download flags a split and refetches only that ticker.
3. **Rows from a different day.** A ticker with no bar on the latest date would have shown an older day's 1D move under "as of". Such rows are now dropped.
4. **Accessibility and touch (ui-reviewer):** no text alternative for the canvas (added a hidden data table), a tap on mobile navigated away instead of showing the tooltip (skipped on coarse pointers), 12px link targets, no colour key, borderline label contrast on the colour-blind palette (canvas colours now cap at a 62% pole mix), and a movers line that implied the best performers of the whole index.
5. **Where I disagreed with a finding.** The verifier flagged IBKR, TKO and BX caps as ~3x below Yahoo's headline company cap. I tested it: `fast_info` returns the same listed-share figure, and the larger number includes unlisted classes and operating units that the index does not weight in full. I kept listed-share sizing and said so in the About text instead of "fixing" it. I also checked a reported encoding bug ("Brown�Forman"): the file stores the en-dash as `–`, it was only the Windows console, so no change.
6. **Not done:** sector average returns in the sector headers (could not be verified against the index, so not shown).

**A slip worth logging.** After the review fixes I chained "run e2e, then commit and push" with the test step piped through `tail`, which hid its exit code, so a commit with 2 failing e2e tests was pushed to the PR branch (not merged; CI would have blocked it). One failure was a flake that passed on rerun. The other was real: the hidden accessibility data table was an `sr-only` `<table>`, and tables ignore `overflow: hidden`, so at 390px the page was 792px wide. Fix: put `sr-only` on a wrapper `div`. Lesson: gate commits on the test command's own exit status, never on a piped one.

## 2026-11-17: AI brief stale for 3 days (fix)
**Failure.** The scheduled run kept the 14 Nov brief. Gemini (`gemini-3.5-flash-lite`) was rejected twice for a leaked `level_pct` field name and the word "guarantee"; Groq answers contradicted the computed regime (GDP "accelerated" at -0.57, core CPI "firmer" at -0.04); Groq's free tier (8000 TPM vs ~7000 per call) answered every retry with 429 because our 4 s/8 s backoff ignored its ~50 s hint, and the feedback retry hit HTTP 413. Meanwhile the header said "Updated 3h ago".
**Fixes.** `pipeline/ai/repair.py` strips leaked field names before validation (never digits; advice words are still rejected); the digest now carries a per-component `state` and the prompt says to only call a component firmer/softer if its state says so; `llm.py` honours Retry-After / "try again in Ns"; if every provider still fails, a code-written auto-summary (validated by the same fact checker) is published and the section is flagged stale so the failure stays visible; the header shows the oldest section refresh plus a "N stale" badge; every panel shows "↻ updated" from `meta.json`.
**Not done.** A second Gemini model was not added: no local key to check model availability and latency (see `ai.yaml` notes).
