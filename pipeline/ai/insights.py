"""AI insights section: code decides the regime, the LLM narrates, the validator checks.

The regime is published separately (regime.json, the `regime` section, which runs first).
This section only adds LLM text: the brief, news clusters and an explainer of that regime.

  inputs = load each JSON once
  regime = regime.json (or computed now if missing)
  digest = build_digest(inputs, regime)            # the model's only source of numbers
  for provider in fallback chain:
      answer = LLM(digest)            → validate → ok? done
      answer = LLM(digest + feedback) → validate → ok? done
  raise InsightsError                  # build.py keeps the previous insights.json (stale)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from ..schemas import Insights
from . import context, llm, validate
from .regime_section import build_regime

log = logging.getLogger("ai.insights")

DISCLAIMER = "AI-generated summary of public data. Not investment advice."

_STR = {"type": "STRING"}
_STR_LIST = {"type": "ARRAY", "items": _STR}
# Gemini responseSchema (OpenAPI subset). Also shown to Groq in its system prompt.
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "brief": {
            "type": "OBJECT",
            "properties": {
                "headline": _STR,
                "bullets": {**_STR_LIST, "minItems": 3, "maxItems": 5},
                "what_moved": _STR,
                "cycle_view": _STR,
            },
            "required": ["headline", "bullets", "what_moved", "cycle_view"],
        },
        "news_clusters": {
            "type": "ARRAY", "maxItems": 6,
            "items": {
                "type": "OBJECT",
                "properties": {"topic": _STR, "summary": _STR, "tags": _STR_LIST, "item_ids": _STR_LIST},
                "required": ["topic", "summary", "tags", "item_ids"],
            },
        },
        "regime_explainer": {
            "type": "OBJECT",
            "properties": {"rationale": _STR, "caveats": {**_STR_LIST, "minItems": 1, "maxItems": 4}},
            "required": ["rationale", "caveats"],
        },
    },
    "required": ["brief", "news_clusters", "regime_explainer"],
}

SYSTEM = """You write the daily macro brief for a public, free markets dashboard.
You receive a JSON digest of today's published dashboard data. It is your ONLY source.
An automatic fact checker reads every sentence you write; follow these rules exactly.

Numbers
1. Every number must be copied from the digest exactly as written there: same digits, same
   decimals, same unit. Never round, compute, average, convert or annualise. If a number is
   not in the digest, describe the move in words without a number.
2. Units come from the digest: keys ending _pct are %, _bp are bp, _pp are percentage
   points (write "pp"), _k are thousands (write "k"), "units" fields give the unit of
   "value"/"prev". Plain index levels have no unit. Write numbers as digits, never words.
3. Put the metric's name right before its number ("core CPI at 2.6%", "the S&P 500 fell
   0.4%"), and use rose/fell words that match the sign of the change in the digest. A
   number after a metric's name must be THAT metric's value; use "from" for a prev value.
4. Market rows are total returns ("ret_*_pct") or yield changes ("chg_*_bp"), not levels.

Regime (digest.regime, decided by deterministic code)
5. Explain it; never override it. Only use the quadrant name(s) in allowed_quadrants. Say
   "boundary" if boundary is true. Describe growth/inflation with the given states
   (accelerating / decelerating / flat): these are directions of change, not levels.
6. Asset tendencies are written by code (regime.tendencies); you may refer to them, but do
   not invent new ones.

Style
7. No advice or predictions: never use buy, sell, overweight, underweight, should,
   recommend, always, every time, guaranteed, or "will" about prices or markets.
8. news_clusters: at most 6 themes from digest.news; item_ids copied exactly from
   digest.news; summaries only say what the headlines say.
9. Plain, neutral English. Headline <= 15 words, bullets <= 30 words each, what_moved and
   cycle_view 2-3 sentences, rationale 2-4 sentences, caveats 1-4 short items.
10. NEVER write the digest's field names (anything with an underscore: level_pct, ret_1w_pct,
    chg_1d_bp...). Say it like a person: "the 10-year yield rose 5 bp to 5.15%", not
    "the 10-year yield level changed with a 5 bp increase to a level_pct of 5.15".
11. Do not invent causes. Say WHAT moved using the digest; only give a reason if a headline in
    digest.news states it, and then attribute it ("headlines point to..."). The headline of
    the brief states a move or theme found in the digest, never an explanation you made up.

Return one JSON object: brief {headline, bullets[3-5], what_moved, cycle_view},
news_clusters [{topic, summary, tags[], item_ids[]}], regime_explainer {rationale, caveats[]}."""


class InsightsError(RuntimeError):
    pass


def build_prompt(digest: dict) -> str:
    return ("Today's dashboard digest (JSON):\n"
            + json.dumps(digest, separators=(",", ":"), ensure_ascii=False)
            + "\n\nWrite the brief, news clusters and regime explainer as JSON.")


def feedback_prompt(base: str, violations: list[str]) -> str:
    listed = "\n".join(f"- {v}" for v in violations[:25])
    return (base + "\n\nYour previous answer was REJECTED by the automatic fact check:\n" + listed
            + "\nRewrite the full JSON fixing every item. Copy numbers exactly from the digest with their "
              "units and the metric name right before them, or describe the move in words without a number.")


def _resolve_clusters(clusters: list[dict], news: dict | None) -> list[dict]:
    by_id = {i["id"]: i for i in (news or {}).get("items", [])}
    out = []
    for c in clusters:
        ids = [i for i in c.get("item_ids", []) if i in by_id]
        out.append({
            "topic": c["topic"], "summary": c["summary"], "tags": [str(t) for t in c.get("tags", [])],
            "item_ids": ids,
            "items": [{k: by_id[i][k] for k in ("id", "title", "url", "source")} for i in ids],
        })
    return out


def load_regime(data_dir: Path, inputs: dict, cfg: dict) -> dict:
    """The published regime.json (written by the `regime` section just before), else compute it."""
    r = context.load(data_dir, "regime")
    if r and r.get("growth_inflation"):
        return r
    return build_regime(data_dir, inputs=inputs, cfg=cfg).model_dump(mode="json")


def build_insights(data_dir: Path, cfg: dict | None = None) -> Insights:
    """Raises llm.NoProviderAvailable (no keys → skip) or InsightsError (all attempts failed)."""
    cfg = cfg or llm.load_config()
    providers = llm.available_providers(cfg)  # NoProviderAvailable before any work

    inputs = context.load_inputs(data_dir)
    if inputs.get("economy") is None:
        raise InsightsError("economy.json missing: cannot build the digest")
    regime = load_regime(data_dir, inputs, cfg)
    digest = context.build_digest(inputs, regime)
    log.info("insights: digest ~%d tokens, providers: %s", context.approx_tokens(digest),
             ", ".join(p.label for p in providers))

    base = build_prompt(digest)
    failures: list[str] = []
    for spec in providers:
        prompt = base
        for attempt in (1, 2):  # second attempt = retry with the violations fed back
            try:
                res = llm.generate(SYSTEM, prompt, RESPONSE_SCHEMA, providers=[spec], cfg=cfg)
            except llm.LLMError as e:
                failures.append(str(e))
                break
            violations = validate.validate(res.data, digest)
            if not violations:
                log.info("insights: accepted from %s (attempt %d)", spec.label, attempt)
                return _assemble(res, regime, inputs, cfg)
            log.warning("insights: %s attempt %d rejected (%d violations): %s", spec.label, attempt,
                        len(violations), "; ".join(violations[:5]))
            failures.append(f"{spec.label} attempt {attempt}: {len(violations)} violations")
            prompt = feedback_prompt(base, violations)
    raise InsightsError("no grounded answer from any provider: " + " | ".join(failures)[:500])


def _assemble(res: llm.LLMResult, regime: dict, inputs: dict, cfg: dict) -> Insights:
    d = res.data
    ex = d["regime_explainer"]
    return Insights.model_validate({
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "provider": res.provider,
        "model": res.model,
        "data_asof": context.data_asof(inputs),
        "about": cfg["about"]["brief"],
        "sources": cfg["brief_sources"] + [{"label": "Fact-check rules (validator)", "url": cfg["validator_url"]}],
        "brief": d["brief"],
        "news_clusters": _resolve_clusters(d.get("news_clusters", []), inputs.get("news")),
        "regime_explainer": {"rationale": ex["rationale"], "caveats": ex["caveats"],
                             "regime_generated_at": regime.get("generated_at"),
                             "regime_label": regime["growth_inflation"].get("label")},
        "disclaimer": DISCLAIMER,
    })
