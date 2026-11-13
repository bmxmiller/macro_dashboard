---
name: add-metric
description: Add a new economic metric to the MacroLens dashboard end to end. Finds the official free data series, registers it with a reviewed About text, rebuilds the data and verifies the value. Use when the user asks to add, track or show a new indicator (e.g. "/add-metric ISM services PMI", "add core goods CPI").
argument-hint: "<metric to add, e.g. 'core goods CPI YoY'>"
---

# Add a metric: $ARGUMENTS

Metrics are **data, not code**. A new metric is one registry entry. Never hardcode a metric in Python or TSX.

## 1. Find the series (free sources only)
- US: search FRED for the official series. With `FRED_API_KEY` set, use
  `https://api.stlouisfed.org/fred/series/search?search_text=...&api_key=$FRED_API_KEY&file_type=json`
  (never print the key). Prefer seasonally adjusted, the longest history, and the publisher's own series (BLS/BEA/Fed/Census) over derived ones.
- UK: use `pipeline/registry/uk.yaml` (BoE IADB / ONS series).
- Confirm the series' frequency, units and last observation date. If no free series exists, stop and tell the user what was checked.

## 2. Choose the transform
| Data | transform | notes |
|---|---|---|
| index level (CPI, PCE, IP) | `yoy` | needs `frequency: monthly` or `quarterly` |
| monthly flow where m/m matters (retail sales) | `mom_pct` | |
| stock where the change matters (payrolls) | `diff` | |
| already a rate/% (unemployment, yields, spreads) | `level` | |
| A ÷ B | `ratio` | `numerator`, `denominator`, `multiplier` |
Use `scale` for unit conversion (e.g. 0.001 for thousands → millions). Set `good` to the direction that is benign **for the economy** (`up`/`down`/`neutral`).

## 3. Write the About text (the finance-awareness showcase)
Three short, accurate paragraphs: `what` (definition + publisher), `why` (why markets and the Fed care), `how_to_read` (thresholds, historical context, caveats and what to cross-check). Plain English, no hype, no investment advice. Every number you quote must be verifiable. Quote YAML strings that start with a quote mark or contain `: `.

## 4. Register it
Add the entry to the right `group` in `pipeline/registry/metrics.yaml`, following the neighbouring entries exactly (`id` in snake_case, `source_url` = the publisher's official page).

## 5. Rebuild and verify
```bash
./.venv/Scripts/python -c "import yaml;yaml.safe_load(open('pipeline/registry/metrics.yaml',encoding='utf-8'))"
./.venv/Scripts/python -m pipeline.build --only economy
```
Then read the new metric back from `web/public/data/economy.json` and check: `value` and `date` match the latest observation on the FRED/official page (after the transform), `history` is non-empty, `period_label` is right. If it disagrees, fix the transform/frequency, don't paper over it.

## 6. Finish
- `./.venv/Scripts/python -m pytest pipeline/tests -q` passes.
- The metric appears automatically in the Economic Indicators panel (no front-end change needed). Mention this.
- Add one line to `docs/AI_WORKFLOW.md` under the current session: the metric, the series chosen and why.
