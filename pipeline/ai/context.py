"""Compact, display-rounded digest of the published JSON for the LLM (target < ~6k tokens).

Every number is rounded the way the dashboard displays it, and every number's unit is explicit
(a key suffix such as ``_pct`` / ``_bp`` / ``_pp`` / ``_k``, or a sibling ``units`` field), so
the validator can check value, unit, sign and label. Duplicated quantities from different
sources (VIX from FRED vs Yahoo, 10Y from the Treasury curve vs ^TNX) carry ``asof``/``source``.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger("ai.context")

MAX_HEADLINES = 40
TOP_N = 3
POSITIONING_EXTREME = (15, 85)
INPUTS = ("markets", "economy", "yield_curve", "uk", "sentiment", "positioning", "news")


def load(data_dir: Path, name: str) -> dict | None:
    p = Path(data_dir) / f"{name}.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.info("digest: %s.json not available", name)
        return None


def load_inputs(data_dir: Path, names=INPUTS) -> dict[str, dict | None]:
    """Parse each input file exactly once; pass the dicts around afterwards."""
    return {n: load(data_dir, n) for n in names}


def _num(v, d: int):
    if v is None:
        return None
    r = round(float(v), d)
    return int(r) if d == 0 else r


def _move(r: dict, period: str) -> dict:
    """Return as displayed: pct → 1dp ``ret_pct``; yields (diff, pp) → whole ``chg_bp``."""
    v = r["returns"].get(period)
    if r.get("mode") == "diff":
        return {"chg_bp": None if v is None else int(round(v * 100))}
    return {"ret_pct": _num(v, 1)}


def markets_digest(markets: dict) -> dict:
    out: dict = {}
    for pid, p in markets.get("panels", {}).items():
        rows = [r for g in p["groups"] for r in g["rows"]]
        if pid == "index_snapshot":
            snap = []
            for r in rows:
                e = {"name": r["name"], "tag": r.get("tag") or r["ticker"],
                     **{f"{k.split('_')[0]}_1d_{k.split('_')[1]}": v for k, v in _move(r, "1D").items()},
                     "asof": r.get("asof"), "source": "Yahoo Finance"}
                # Equity rows are ETF proxies (SPY, DIA…): their price is not the index level.
                if not r["ticker"].isalpha():
                    e["level_pct" if r.get("mode") == "diff" else "level"] = _num(r.get("price"), 2)
                snap.append(e)
            out["index_snapshot"] = snap
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
            entry = lambda r: {"name": r["name"], "tag": r.get("tag") or r["ticker"], **_move(r, period)}  # noqa: E731
            panel[period] = {"top": [entry(r) for r in ranked[:TOP_N]],
                             "bottom": [entry(r) for r in ranked[-TOP_N:][::-1]]}
        out[p["title"]] = panel
    return out


def _metric(m: dict, source: str) -> dict:
    d = m.get("decimals", 1)
    return {"name": m["name"], "value": _num(m.get("value"), d), "prev": _num(m.get("prev"), d),
            "units": m.get("units") or "", "period": m.get("period_label"),
            "z": _num(m.get("zscore"), 1), "source": source}


def yield_digest(yc: dict) -> dict:
    return {
        "asof": yc.get("asof"), "source": "FRED (US Treasury par yields, daily close)",
        "tenors_pct": {p["label"]: _num(p.get("now"), 2) for p in yc.get("points", []) if p.get("now") is not None},
        "spreads": [{"label": s["label"], "value_pct": _num(s["value"], 2), "value_bp": int(round(s["value"] * 100)),
                     "chg_1m_bp": int(round((s["value"] - s["m1"]) * 100)) if s.get("m1") is not None else None}
                    for s in yc.get("spreads", [])],
    }


def sentiment_digest(s: dict) -> dict:
    out = {}
    fg = s.get("fear_greed")
    if fg:
        out["fear_greed"] = {"score": _num(fg["score"], 0), "rating": fg.get("rating"),
                             "score_1w_ago": _num(fg.get("previous_1_week"), 0),
                             "score_1m_ago": _num(fg.get("previous_1_month"), 0), "source": "CNN"}
    vt = s.get("vix_term")
    if vt:
        out["vix_term"] = {"vix": _num(vt["vix"], 1), "vix3m": _num(vt["vix3m"], 1), "ratio": _num(vt["ratio"], 2),
                           "state": vt["state"], "pctile_1y": _num(vt.get("percentile_1y"), 0),
                           "asof": vt.get("asof"), "source": "Cboe via Yahoo Finance"}
    return out


def position_text(net: float, pct: float, hi: float = POSITIONING_EXTREME[1]) -> str:
    """Sign-aware: the top of the 3y range is 'most net long' only if the position is long."""
    if pct > hi:
        return "most net long in 3y" if net > 0 else "least net short in 3y"
    return "most net short in 3y" if net < 0 else "least net long in 3y"


def positioning_digest(p: dict) -> list[dict]:
    lo, hi = POSITIONING_EXTREME
    out = []
    for m in p.get("markets", []):
        pct = m.get("percentile_3y")
        if pct is None or lo <= pct <= hi:
            continue
        out.append({"name": m["name"], "group": m["trader_group"], "pctile_3y": _num(pct, 0),
                    "net_pct_oi": _num(m.get("net_pct_oi"), 1), "side": "net long" if m["net"] > 0 else "net short",
                    "position": position_text(m["net"], pct), "asof": m.get("report_date"), "source": "CFTC COT"})
    return out


def news_digest(n: dict) -> list[dict]:
    items = sorted(n.get("items", []), key=lambda i: i.get("published", ""), reverse=True)[:MAX_HEADLINES]
    return [{"id": i["id"], "source": i["source"], "title": i["title"]} for i in items]


def _component_state(score) -> str:
    """Same ±0.1 thresholds as the validator, spelled out so the model never has to infer a direction."""
    if not isinstance(score, (int, float)):
        return "flat"
    return "accelerating" if score >= 0.1 else "decelerating" if score <= -0.1 else "flat"


def regime_digest(regime: dict) -> dict:
    """The code-computed regime, with unit-suffixed fields the model may quote."""
    gi = regime["growth_inflation"]

    def side(x: dict) -> dict:
        return {"score": x["score"], "state": x["state"],
                "components": [{"label": c["label"], "metric": c["metric"],
                                f"value_{c['units'] if c['units'] != '%' else 'pct'}": c["value"],
                                "score": c["score"], "state": _component_state(c["score"]),
                                **c["detail"]} for c in x["components"]]}
    gp = {k: v for k, v in regime["growth_policy"].items() if k not in ("growth_direction", "note")}
    cd = {k: v for k, v in regime["credit_duration"].items()}
    return {"growth_inflation": {"quadrant": gi["quadrant"], "label": gi["label"], "boundary": gi["boundary"],
                                 "allowed_quadrants": gi["allowed_quadrants"],
                                 "growth": side(gi["growth"]), "inflation": side(gi["inflation"]),
                                 "core_pce_pct": gi["core_pce_pct"], "inflation_target_pct": gi["inflation_target_pct"]},
            "growth_policy": gp, "credit_duration": cd,
            "tendencies": [t["text"] for t in (regime.get("tendencies") or {}).get("items", [])]}


def build_digest(inputs: dict[str, dict | None], regime: dict | None = None) -> dict:
    """The LLM's whole world: nothing outside this dict may be quoted as a number."""
    d: dict = {}
    if (m := inputs.get("markets")):
        d["markets"] = markets_digest(m)
    if (e := inputs.get("economy")):
        d["economy"] = {m["id"]: _metric(m, "FRED") for m in e.get("metrics", [])}
    if (y := inputs.get("yield_curve")):
        d["yield_curve"] = yield_digest(y)
    if (u := inputs.get("uk")):
        d["uk"] = {m["id"]: _metric(m, "ONS / Bank of England") for m in u.get("metrics", [])}
    if (s := inputs.get("sentiment")):
        d["sentiment"] = sentiment_digest(s)
    if (p := inputs.get("positioning")):
        d["positioning_extremes"] = positioning_digest(p)
    if (n := inputs.get("news")):
        d["news"] = news_digest(n)
    if regime:
        d["regime"] = regime_digest(regime)
    return d


def data_asof(inputs: dict[str, dict | None]) -> str | None:
    """Latest generated_at among the input files."""
    stamps = [x["generated_at"] for x in inputs.values() if x and x.get("generated_at")]
    return max(stamps) if stamps else None


def approx_tokens(obj) -> int:
    """~4 characters per token: a conservative size check without a tokenizer."""
    return len(json.dumps(obj, separators=(",", ":"), ensure_ascii=False)) // 4
