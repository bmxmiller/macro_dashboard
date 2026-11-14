"""Deterministic macro regime lenses. **Code decides, the LLM only narrates.**

All inputs come from the published JSON (economy.json metric histories, markets.json
returns), so the result is reproducible from what the dashboard shows.

1. Growth × Inflation (Gave / Bridgewater-style four quadrants)
   growth score    = mean of the available components, each clipped to [−1, 1]:
     * INDPRO YoY, change over 6 months             ÷ 2.0pp
     * initial claims, −(4-week avg / 26-week avg − 1) ÷ 0.10   (rising claims = weaker growth)
     * real GDP QoQ SAAR − 1.8% trend                 ÷ 2.0pp
   inflation score = mean of: core CPI YoY and core PCE YoY, change over 6 months ÷ 1.0pp
   direction: score > 0 → "up", otherwise "down" (0 counts as down: no acceleration).
   |score| < 0.1 is flagged ``borderline``.
     growth up   + inflation up   → Reflation
     growth up   + inflation down → Goldilocks
     growth down + inflation up   → Stagflation
     growth down + inflation down → Deflationary slowdown
   A side with no usable component gives quadrant ``None`` (insufficient data).

2. Growth × Policy
   real policy rate = Fed funds upper bound − core PCE YoY.
   > 1.0% restrictive, < 0.5% accommodative, otherwise neutral (≈ r* band), crossed with
   the growth direction from lens 1.

3. Credit × Duration
   3-month total return spread HYG − TLT and LQD − IEF; mean > +0.5pp → credit leading,
   < −0.5pp → duration leading, otherwise balanced.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

GDP_TREND = 1.8
NEUTRAL_BAND = (0.5, 1.0)
BORDERLINE = 0.1
CREDIT_DEADBAND = 0.5
QUADRANTS = {
    ("up", "up"): "Reflation",
    ("up", "down"): "Goldilocks",
    ("down", "up"): "Stagflation",
    ("down", "down"): "Deflationary slowdown",
}
CREDIT_PAIRS = [("HYG", "TLT"), ("LQD", "IEF")]


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def _r(x: float | None, d: int = 2) -> float | None:
    return None if x is None else round(float(x), d)


def series(metrics: dict[str, dict], mid: str) -> pd.Series:
    """Metric history ([[date, value], ...]) as a date-indexed Series (empty if missing)."""
    m = metrics.get(mid)
    if not m or not m.get("history"):
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in m["history"]}, dtype=float)
    return s.sort_index().dropna()


def change_over(s: pd.Series, months: int = 6) -> tuple[float, float, float] | None:
    """(latest, value `months` earlier, change). Uses the last obs on/before the target date."""
    if s.empty:
        return None
    last_d = s.index[-1]
    earlier = s.loc[:last_d - pd.DateOffset(months=months)]
    if earlier.empty:
        return None
    now, then = float(s.iloc[-1]), float(earlier.iloc[-1])
    return now, then, now - then


def claims_trend(s: pd.Series) -> tuple[float, float, float] | None:
    """(4-week avg, 26-week avg, ratio − 1) from weekly initial claims."""
    s = s.dropna()
    if len(s) < 26:
        return None
    ma4, ma26 = float(s.iloc[-4:].mean()), float(s.iloc[-26:].mean())
    if ma26 == 0:
        return None
    return ma4, ma26, ma4 / ma26 - 1


def _direction(score: float) -> str:
    return "up" if score > 0 else "down"


def growth_signal(metrics: dict[str, dict]) -> dict:
    comps: list[dict] = []
    ip = change_over(series(metrics, "indpro_yoy"))
    if ip:
        comps.append({"id": "indpro", "label": "Industrial production YoY, 6m change",
                      "value": _r(ip[2]), "units": "pp", "detail": {"now": _r(ip[0]), "6m_ago": _r(ip[1])},
                      "score": _r(_clip(ip[2] / 2.0))})
    cl = claims_trend(series(metrics, "claims"))
    if cl:
        comps.append({"id": "claims", "label": "Initial claims 4w vs 26w avg (inverted)",
                      "value": _r(cl[2] * 100, 1), "units": "%", "detail": {"avg_4w": _r(cl[0], 1), "avg_26w": _r(cl[1], 1)},
                      "score": _r(_clip(-cl[2] / 0.10))})
    gdp = series(metrics, "gdp_qoq")
    if not gdp.empty:
        g = float(gdp.iloc[-1])
        comps.append({"id": "gdp", "label": f"Real GDP QoQ SAAR vs {GDP_TREND}% trend",
                      "value": _r(g - GDP_TREND, 1), "units": "pp", "detail": {"gdp": _r(g, 1), "trend": GDP_TREND},
                      "score": _r(_clip((g - GDP_TREND) / 2.0))})
    return _combine(comps)


def inflation_signal(metrics: dict[str, dict]) -> dict:
    comps: list[dict] = []
    for mid, label in (("core_cpi_yoy", "Core CPI YoY, 6m change"), ("core_pce_yoy", "Core PCE YoY, 6m change")):
        c = change_over(series(metrics, mid))
        if c:
            comps.append({"id": mid, "label": label, "value": _r(c[2]), "units": "pp",
                          "detail": {"now": _r(c[0]), "6m_ago": _r(c[1])}, "score": _r(_clip(c[2] / 1.0))})
    return _combine(comps)


def _combine(comps: list[dict]) -> dict:
    if not comps:
        return {"score": None, "direction": None, "components": []}
    score = round(sum(c["score"] for c in comps) / len(comps), 2)
    return {"score": score, "direction": _direction(score), "components": comps}


def growth_inflation(metrics: dict[str, dict]) -> dict:
    g, i = growth_signal(metrics), inflation_signal(metrics)
    quadrant = None
    if g["direction"] and i["direction"]:
        quadrant = QUADRANTS[(g["direction"], i["direction"])]
    borderline = any(x["score"] is not None and abs(x["score"]) < BORDERLINE for x in (g, i))
    return {"quadrant": quadrant, "growth": g, "inflation": i, "borderline": borderline}


def policy_stance(real_rate: float) -> str:
    lo, hi = NEUTRAL_BAND
    if real_rate > hi:
        return "restrictive"
    if real_rate < lo:
        return "accommodative"
    return "neutral"


def growth_policy(metrics: dict[str, dict], growth_direction: str | None) -> dict:
    ff, pce = metrics.get("fed_funds"), metrics.get("core_pce_yoy")
    if not ff or not pce or ff.get("value") is None or pce.get("value") is None:
        return {"label": None, "stance": None, "real_rate": None, "growth_direction": growth_direction}
    fed, core = round(float(ff["value"]), 2), round(float(pce["value"]), 1)
    real = round(fed - core, 2)
    stance = policy_stance(real)
    label = f"{stance.capitalize()} policy, growth {'rising' if growth_direction == 'up' else 'slowing'}" \
        if growth_direction else f"{stance.capitalize()} policy"
    return {"label": label, "stance": stance, "real_rate": real, "fed_funds": fed, "core_pce": core,
            "neutral_band": list(NEUTRAL_BAND), "growth_direction": growth_direction}


def _rows_by_ticker(markets: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in (markets or {}).get("panels", {}).values():
        for g in p.get("groups", []):
            for r in g.get("rows", []):
                out.setdefault(r["ticker"], r)
    return out


def credit_duration(markets: dict, period: str = "3M") -> dict:
    rows = _rows_by_ticker(markets)
    pairs = []
    for long, short in CREDIT_PAIRS:
        a = (rows.get(long) or {}).get("returns", {}).get(period)
        b = (rows.get(short) or {}).get("returns", {}).get(period)
        if a is None or b is None:
            continue
        a, b = round(float(a), 1), round(float(b), 1)
        pairs.append({"long": long, "short": short, "long_ret": a, "short_ret": b, "spread": round(a - b, 1)})
    if not pairs:
        return {"label": None, "leader": None, "score": None, "period": period, "pairs": []}
    score = round(sum(p["spread"] for p in pairs) / len(pairs), 1)
    if score > CREDIT_DEADBAND:
        leader, label = "credit", "Credit leading duration"
    elif score < -CREDIT_DEADBAND:
        leader, label = "duration", "Duration leading credit"
    else:
        leader, label = "balanced", "Credit and duration balanced"
    return {"label": label, "leader": leader, "score": score, "period": period, "pairs": pairs}


def compute_regime(economy: dict | None, markets: dict | None) -> dict[str, Any]:
    metrics = {m["id"]: m for m in (economy or {}).get("metrics", [])}
    gi = growth_inflation(metrics)
    return {
        "growth_inflation": gi,
        "growth_policy": growth_policy(metrics, gi["growth"]["direction"]),
        "credit_duration": credit_duration(markets or {}),
    }
