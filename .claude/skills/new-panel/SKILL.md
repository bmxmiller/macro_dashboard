---
name: new-panel
description: Add a new dashboard panel to MacroLens end to end: data contract, panel component on the shared Panel shell, registry entry, About text, stale handling, e2e coverage and a visual check. Use when the user asks to show a new dataset or chart as a panel.
argument-hint: "<panel to add, e.g. 'central bank balance sheets'>"
---

# Add a panel: $ARGUMENTS

A panel is data + a component + one line in the registry. Don't build a bespoke layout when the shared pieces fit. For a new **metric** in an existing list (not a new panel) use `/add-metric` instead.

## 1. Data first
- Does the JSON section already exist in `web/public/data/`? If not, add a pipeline section: a fetcher in `pipeline/fetchers/`, a build function plus entry in `SECTIONS` / `EXTRA_BUILDERS` in `pipeline/build.py`, a pydantic model in `pipeline/schemas.py`, and a registry YAML in `pipeline/registry/` holding the About texts. All HTTP goes through `pipeline/fetchers/http.py` (never change the global User-Agent: FRED stalls browser-like ones; pass per-request `browser_headers()` for hosts that need them).
- Free sources only. Check the source works without a paid key.
- Add the matching TypeScript interface to `web/src/types.ts` (same field names as the pydantic model).
- Run the section: `./.venv/Scripts/python -m pipeline.build --only <section>`. Read the JSON and sanity-check the values against the official source page.

## 2. The component (`web/src/panels/<Name>.tsx`)
Copy the pattern from `PerformancePanel.tsx` (simple list) or `EconomicIndicators.tsx` / `components/MetricList.tsx` (metrics with history modal):
- `useData<T>("<section>")` for the data and `useStale("<section>")` for the Stale badge; render `Loading…`, an error message, and an empty state.
- Wrap in `<Panel id title subtitle about sourceUrl stale>`. The `about` object is `{what, why, how_to_read}` and is required; put extra per-feed or per-row detail in `aboutExtra`.
- Formatting only from `web/src/lib/format.ts` (`signed`, `fmtValue`, `perfBg`, `relTime`, `safeUrl`, `ordinal`…). Signed numbers with +/− so colour is never the only cue. Colours only from CSS tokens (`var(--ink)`, `--accent`, `--pos`/`--neg`), never raw hex. Only render `http(s)` links from external data via `safeUrl`.
- Every row or metric that shows a number needs its own ⓘ About and a link to its official source.
- Charts: use `components/LazyEChart.tsx` (lazy loaded) and `chartTheme.ts`; read colours from tokens.

## 3. Register it
Add one entry to `PANELS` in `web/src/panels/registry.tsx`, starting with `{ id: "...", title: "..."` exactly like its neighbours (the e2e tests parse that pattern). Pick the `section` from `SECTIONS` (add a new section name there if needed; the Customise View menu derives from it), a `span`, and `tall` if it needs two rows. The `id` must equal the `<Panel id>`.

## 4. Tests
- If the pipeline gained logic, add offline pytest tests for the pure parts (no network).
- The Playwright suite (`web/e2e/dashboard.spec.ts`) discovers panels from the registry, checks the title renders, that no "Could not load data" appears when the JSON exists, and that there are no console errors. If your section isn't in `CORE_SECTIONS`, the generic check covers it. Add a specific assertion only for non-obvious behaviour (a filter, a modal).

## 5. Verify
```bash
./.venv/Scripts/python -m pytest -q
cd web && npm run typecheck && npm run build && npm run test:e2e
```
Look at the result (the e2e run writes screenshots to `web/e2e/__screenshots__/actual/`): dark, light and mobile. Check units, signs, empty and stale states, and that nothing clips.

## 6. Ship it
Branch, PR, CI, `/code-review`, and (for anything showing numbers) the `finance-reviewer` agent. See `/ship-feature` for the full flow. `main` is protected, so there are no direct pushes.
