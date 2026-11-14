"""Compact, display-rounded digest of the published JSON for the LLM (target < ~6k tokens).

Every number is rounded the way the dashboard displays it (returns 1dp %, yield moves in
whole bp, metrics at their registry decimals), so the model can only quote what a reader
would see, and the validator can check its numbers against this dict.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("ai.context")

MAX_HEADLINES = 40
TOP_N = 3
POSITIONING_EXTREME = (15, 85)


def load(data_dir: Path, name: str) -> dict | None:
    p = Path(data_dir) / f"{name}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.info("digest: %s.json not available", name)
        return None


def _ret(v, mode: str):
    """Return as displayed: pct → 1dp %, diff (yields, pp) → whole bp."""
    if v is None:
        return None
    return int(round(v * 100)) if mode == "diff" else round(float(v), 1)


def _num(v, d: int):
    if v is None:
        return None
    r = round(float(v), d)
    return int(r) if d == 0 else r


def _market_entry(r: dict, period: str) -> dict:
    unit = "bp" if r.get("mode") == "diff" else "%"
    return {"name": r["name"], "tag": r.get("tag") or r["ticker"], "ret": _ret(r["returns"].get(period), r.get("mode", "pct")),
            "unit": unit}


def markets_digest(markets: dict) -> dict:
    out: dict = {}
    for pid, p in markets.get("panels", {}).items():
        rows = [r for g in p["groups"] for r in g["rows"]]
        if pid == "index_snapshot":
            # Equity rows are ETF proxies (SPY, DIA…): their price is not the index level, so
            # omit it rather than let the model write "Dow Jones 523". Keep true levels (^VIX, futures…).
            out["index_snapshot_1D"] = [
                {**_market_entry(r, "1D"), **({} if r["ticker"].isalpha() else {"level": _num(r.get("price"), 2)})}
                for r in rows]
            continue
        seen, uniq = set(), []
        for r in rows:  # SPY appears as a sector benchmark too
            if r["ticker"] not in seen:
                seen.add(r["ticker"])
                uniq.append(r)
        panel = {}
        for period in ("1W", "1M"):
            ranked = sorted((r for r in uniq if r["returns"].get(period) is not None),
                            key=lambda r: r["returns"][period], reverse=True)
            panel[period] = {"top": [_market_entry(r, period) for r in ranked[:TOP_N]],
                             "bottom": [_market_entry(r, period) for r in ranked[-TOP_N:][::-1]]}
        out[p["title"]] = panel
    return out


def _metric(m: dict) -> dict:
    d = m.get("decimals", 1)
    return {"name": m["name"], "value": _num(m.get("value"), d), "prev": _num(m.get("prev"), d),
            "units": m.get("units") or "", "period": m.get("period_label"),
            "z": _num(m.get("zscore"), 1)}


def yield_digest(yc: dict) -> dict:
    return {
        "asof": yc.get("asof"),
        "tenors_pct": {p["label"]: _num(p.get("now"), 2) for p in yc.get("points", []) if p.get("now") is not None},
        "spreads": [{"label": s["label"], "value_pct": _num(s["value"], 2), "value_bp": int(round(s["value"] * 100)),
                     "change_1m_bp": int(round((s["value"] - s["m1"]) * 100)) if s.get("m1") is not None else None}
                    for s in yc.get("spreads", [])],
    }


def sentiment_digest(s: dict) -> dict:
    out = {}
    fg = s.get("fear_greed")
    if fg:
        out["fear_greed"] = {"score": _num(fg["score"], 0), "rating": fg.get("rating"),
                             "1w_ago": _num(fg.get("previous_1_week"), 0),
                             "1m_ago": _num(fg.get("previous_1_month"), 0)}
    vt = s.get("vix_term")
    if vt:
        out["vix"] = {"vix": _num(vt["vix"], 1), "vix3m": _num(vt["vix3m"], 1), "ratio": _num(vt["ratio"], 2),
                      "state": vt["state"], "pct_1y": _num(vt.get("percentile_1y"), 0)}
    return out


def positioning_digest(p: dict) -> list[dict]:
    lo, hi = POSITIONING_EXTREME
    out = []
    for m in p.get("markets", []):
        pct = m.get("percentile_3y")
        if pct is None or lo <= pct <= hi:
            continue
        out.append({"name": m["name"], "group": m["trader_group"], "pctile_3y": _num(pct, 0),
                    "net_pct_oi": _num(m.get("net_pct_oi"), 1), "side": "net long" if m["net"] > 0 else "net short",
                    "extreme": "near 3y high of net position" if pct > hi else "near 3y low of net position"})
    return out


def news_digest(n: dict) -> list[dict]:
    items = sorted(n.get("items", []), key=lambda i: i.get("published", ""), reverse=True)[:MAX_HEADLINES]
    return [{"id": i["id"], "source": i["source"], "title": i["title"]} for i in items]


def _regime_digest(regime: dict) -> dict:
    """Regime result without verbose labels the model doesn't need."""
    gi = regime["growth_inflation"]
    side = lambda x: {"score": x["score"], "direction": x["direction"],  # noqa: E731
                      "components": [{"label": c["label"], "value": c["value"], "units": c["units"],
                                      "score": c["score"], **c["detail"]} for c in x["components"]]}
    gp = {k: regime["growth_policy"].get(k) for k in ("label", "stance", "real_rate", "fed_funds", "core_pce", "neutral_band")}
    cd = {k: regime["credit_duration"].get(k) for k in ("label", "leader", "score", "period", "pairs")}
    return {"growth_inflation": {"quadrant": gi["quadrant"], "borderline": gi["borderline"],
                                 "growth": side(gi["growth"]), "inflation": side(gi["inflation"])},
            "growth_policy": gp, "credit_duration": cd}


def build_digest(data_dir: Path, regime: dict | None = None) -> dict:
    """The LLM's whole world: nothing outside this dict may be quoted as a number."""
    d: dict = {}
    if (m := load(data_dir, "markets")):
        d["markets"] = markets_digest(m)
    if (e := load(data_dir, "economy")):
        d["economy"] = {m["id"]: _metric(m) for m in e.get("metrics", [])}
    if (y := load(data_dir, "yield_curve")):
        d["yield_curve"] = yield_digest(y)
    if (u := load(data_dir, "uk")):
        d["uk"] = {m["id"]: _metric(m) for m in u.get("metrics", [])}
    if (s := load(data_dir, "sentiment")):
        d["sentiment"] = sentiment_digest(s)
    if (p := load(data_dir, "positioning")):
        d["positioning_extremes"] = positioning_digest(p)
    if (n := load(data_dir, "news")):
        d["news"] = news_digest(n)
    if regime:
        d["regime"] = _regime_digest(regime)
    return d


def data_asof(data_dir: Path) -> str | None:
    """Latest generated_at among the input files."""
    stamps = [x["generated_at"] for name in ("markets", "economy", "yield_curve", "uk", "sentiment", "positioning", "news")
              if (x := load(data_dir, name)) and x.get("generated_at")]
    return max(stamps) if stamps else None


def approx_tokens(obj) -> int:
    """~4 characters per token: a conservative size check without a tokenizer."""
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False)) // 4
