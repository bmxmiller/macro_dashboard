"""AI insights section: code decides the regime, the LLM narrates, the validator checks.

Flow (one LLM call on the happy path):
  regime = compute_regime(economy, markets)       # deterministic
  digest = build_digest(data_dir, regime)          # the model's only source of numbers
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
from .regime import compute_regime

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
            "properties": {
                "rationale": _STR,
                "asset_tendencies": {**_STR_LIST, "minItems": 1, "maxItems": 6},
                "caveats": {**_STR_LIST, "minItems": 1, "maxItems": 6},
            },
            "required": ["rationale", "asset_tendencies", "caveats"],
        },
    },
    "required": ["brief", "news_clusters", "regime_explainer"],
}

SYSTEM = """You write the daily macro brief for a public, free markets dashboard.
You receive a JSON digest of today's published dashboard data. It is your ONLY source.

Hard rules:
1. Every number you write must appear in the digest, with the same rounding and units
   (returns in %, yield/spread moves in bp, metrics in their listed units). Never compute
   new numbers (no differences, sums, averages, annualising or unit conversions). If a
   number is not in the digest, describe the direction in words instead.
2. The macro regime (digest.regime) was decided by deterministic rules. Explain it; never
   override or second-guess the quadrant, stance or leader. Mention if it is borderline.
3. news_clusters: group the headlines in digest.news into at most 6 themes. item_ids must be
   ids copied exactly from digest.news. Summaries describe what the headlines say; do not
   add facts that are not in them.
4. No investment advice, recommendations, price targets or forecasts stated as fact.
   "Historical tendencies" are generalisations about past regimes, phrased as such.
5. Plain, neutral English. Be concise: headline <= 15 words, each bullet <= 30 words,
   what_moved and cycle_view 2-3 sentences each, rationale 2-4 sentences.

Return a single JSON object with keys brief {headline, bullets[3-5], what_moved, cycle_view},
news_clusters [{topic, summary, tags[], item_ids[]}], regime_explainer {rationale,
asset_tendencies[], caveats[]}."""


class InsightsError(RuntimeError):
    pass


def build_prompt(digest: dict) -> str:
    return ("Today's dashboard digest (JSON):\n"
            + json.dumps(digest, separators=(",", ":"), ensure_ascii=False)
            + "\n\nWrite the brief, news clusters and regime explainer as JSON.")


def feedback_prompt(base: str, violations: list[str]) -> str:
    listed = "\n".join(f"- {v}" for v in violations[:20])
    return (base + "\n\nYour previous answer was REJECTED by an automatic fact check:\n" + listed
            + "\nRewrite the full JSON. Remove or replace every number that is not in the digest "
              "(use words like 'rose' or 'fell' instead), and fix any structural problems.")


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


def build_insights(data_dir: Path, cfg: dict | None = None) -> Insights:
    """Raises llm.NoProviderAvailable (no keys → skip) or InsightsError (all attempts failed)."""
    cfg = cfg or llm.load_config()
    providers = llm.available_providers(cfg)  # NoProviderAvailable before any work

    economy, markets = context.load(data_dir, "economy"), context.load(data_dir, "markets")
    if economy is None:
        raise InsightsError("economy.json missing: cannot compute the regime")
    regime = compute_regime(economy, markets)
    digest = context.build_digest(data_dir, regime)
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
                return _assemble(res, regime, data_dir, cfg)
            log.warning("insights: %s attempt %d rejected (%d violations): %s", spec.label, attempt,
                        len(violations), "; ".join(violations[:5]))
            failures.append(f"{spec.label} attempt {attempt}: {len(violations)} violations")
            prompt = feedback_prompt(base, violations)
    raise InsightsError("no grounded answer from any provider: " + " | ".join(failures)[:500])


def _assemble(res: llm.LLMResult, regime: dict, data_dir: Path, cfg: dict) -> Insights:
    d = res.data
    return Insights.model_validate({
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "provider": res.provider,
        "model": res.model,
        "data_asof": context.data_asof(data_dir),
        "about": cfg["about"],
        "brief": d["brief"],
        "news_clusters": _resolve_clusters(d.get("news_clusters", []), context.load(data_dir, "news")),
        "regime": {**regime, "explainer": d["regime_explainer"]},
        "disclaimer": DISCLAIMER,
    })
