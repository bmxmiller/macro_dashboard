"""`regime` pipeline section: publish the code-computed regime as regime.json (no LLM, no keys)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..schemas import Regime
from . import context, llm
from .regime import CREDIT_PAIRS, compute_regime

SOURCE_METRICS = ["indpro_yoy", "claims", "gdp_qoq", "core_cpi_yoy", "core_pce_yoy", "fed_funds", "hy_oas"]


def _sources(economy: dict | None, markets: dict | None) -> list[dict[str, str]]:
    """Exact series behind the lenses, linked to their official pages (from the published JSON)."""
    out = []
    metrics = {m["id"]: m for m in (economy or {}).get("metrics", [])}
    for mid in SOURCE_METRICS:
        if (m := metrics.get(mid)):
            out.append({"label": f"{m['name']} (FRED)", "url": m.get("data_url") or m["source_url"]})
    tickers = {t for pair in CREDIT_PAIRS for t in pair}
    seen = set()
    for p in (markets or {}).get("panels", {}).values():
        for g in p.get("groups", []):
            for r in g.get("rows", []):
                if r["ticker"] in tickers and r["ticker"] not in seen:
                    seen.add(r["ticker"])
                    out.append({"label": f"{r['ticker']} {r['name']} (Yahoo Finance)", "url": r["source_url"]})
    return out


def tendencies_for(quadrant: str | None, cfg: dict) -> dict:
    t = cfg["regime_tendencies"]
    return {"quadrant": quadrant, "items": t["quadrants"].get(quadrant, []) if quadrant else [], "basis": t["basis"]}


def build_regime(data_dir: Path, inputs: dict | None = None, cfg: dict | None = None, today=None) -> Regime:
    cfg = cfg or llm.load_config()
    inputs = inputs or context.load_inputs(data_dir, ("economy", "markets"))
    economy, markets = inputs.get("economy"), inputs.get("markets")
    if economy is None:
        raise RuntimeError("economy.json missing: cannot compute the regime")
    r = compute_regime(economy, markets, today=today)
    stamps = [x["generated_at"] for x in (economy, markets) if x and x.get("generated_at")]
    return Regime.model_validate({
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "data_asof": max(stamps) if stamps else None,
        "about": cfg["about"]["regime"],
        "methodology_url": cfg["methodology_url"],
        "sources": _sources(economy, markets),
        **r,
        "tendencies": tendencies_for(r["growth_inflation"]["quadrant"], cfg),
    })
