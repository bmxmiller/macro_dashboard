"""Deterministic macro regime lenses. **Code decides, the LLM only narrates.**

Inputs are the published JSON (economy.json metric histories, markets.json returns), so the
result is reproducible from what the dashboard shows. Published as ``regime.json`` by its own
pipeline section, independent of any LLM key.

1. Growth × Inflation momentum quadrant (Investment-Clock style: the *direction of change*
   of growth and inflation, not their level).
   growth score    = mean of the available components, each clipped to [−1, 1]:
     * Industrial production YoY, change over 6 months ÷ 2.0pp
     * initial claims: −(4-week avg ÷ 26-week avg − 1) ÷ 10%. A 4-week average 10% above the
       26-week average scores −1; a sustained 10% jump in claims scores ≈ −0.83, because the
       26-week average already contains the 4 recent weeks.
     * real GDP momentum: YoY growth (compounded from the QoQ SAAR prints) minus its value
       2 quarters earlier, ÷ 1.0pp
   inflation score = mean of: core CPI YoY and core PCE YoY, change over 6 months ÷ 1.0pp
   axis state: score ≥ +0.1 accelerating, ≤ −0.1 decelerating, otherwise flat.
   quadrant (by sign; 0 counts as down):
     growth up   + inflation up   → Inflationary boom
     growth up   + inflation down → Goldilocks
     growth down + inflation up   → Stagflation
     growth down + inflation down → Disinflationary slowdown
   A flat axis is shown as a boundary, e.g. "Goldilocks / Inflationary boom boundary".

2. Growth × Policy
   real policy rate = Fed funds target-range midpoint (upper − 0.125) − core PCE YoY,
   classified on unrounded values: > 1.0% restrictive, < 0.5% accommodative, else neutral.
   Within 0.15pp of a band edge is flagged borderline. r* is uncertain (FOMC longer-run
   projections imply ≈1%; Holston-Laubach-Williams estimates ≈0.7–1.3%).

3. Credit × Duration
   3-month total-return spread of duration-matched pairs, HYG − IEI and LQD − IEF; mean
   > +0.5pp → credit leading, < −0.5pp → duration leading, else balanced; within 0.25pp of
   ±0.5 is borderline. The 3-month change in the HY option-adjusted spread is shown as a
   cross-check (tighter spreads confirm credit leadership).

Data hygiene: a 6-month comparison needs an observation within 35 days of the target date,
and each input is dropped (and listed in ``stale_inputs``) if its latest period ended too
long ago (weekly 31 days, monthly 120, quarterly 152, daily 14).
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

FLAT = 0.1
NEUTRAL_BAND = (0.5, 1.0)
POLICY_BORDERLINE = 0.15
CREDIT_DEADBAND = 0.5
CREDIT_BORDERLINE = 0.25
INFLATION_TARGET = 2.0
COMPARE_TOLERANCE_DAYS = 35
STALE_DAYS = {"weekly": 31, "monthly": 120, "quarterly": 152, "daily": 14}
QUADRANTS = {
    ("up", "up"): "Inflationary boom",
    ("up", "down"): "Goldilocks",
    ("down", "up"): "Stagflation",
    ("down", "down"): "Disinflationary slowdown",
}
CREDIT_PAIRS = [("HYG", "IEI"), ("LQD", "IEF")]  # duration-matched (≈3.5–4y and ≈7–8y)
R_STAR_NOTE = ("r* (the neutral real rate) is uncertain: FOMC longer-run projections imply about 1%, "
               "Holston-Laubach-Williams estimates range about 0.7–1.3%.")


def _clip(x: float) -> float:
    return max(-1.0, min(1.0, x))


def _r(x: float | None, d: int = 2) -> float | None:
    return None if x is None else round(float(x), d)


def _today(today) -> pd.Timestamp:
    return pd.Timestamp(today or date.today()).normalize()


def series(metrics: dict[str, dict], mid: str) -> pd.Series:
    """Metric history ([[date, value], ...]) as a date-indexed Series (empty if missing)."""
    m = metrics.get(mid)
    if not m or not m.get("history"):
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(d): float(v) for d, v in m["history"]}, dtype=float)
    return s.sort_index().dropna()


def period_end(d: pd.Timestamp, frequency: str) -> pd.Timestamp:
    if frequency == "monthly":
        return d + pd.offsets.MonthEnd(0)
    if frequency == "quarterly":
        return d + pd.offsets.QuarterEnd(0)
    return d


def is_stale(s: pd.Series, frequency: str, today) -> bool:
    if s.empty:
        return True
    age = (_today(today) - period_end(s.index[-1], frequency)).days
    return age > STALE_DAYS.get(frequency, 120)


def change_over(s: pd.Series, months: int = 6,
                tolerance_days: int = COMPARE_TOLERANCE_DAYS) -> tuple[float, float, float] | None:
    """(latest, value `months` earlier, change), or None if there is no observation within
    `tolerance_days` on/before the target date (a gap would silently stretch the window)."""
    if s.empty:
        return None
    last_d = s.index[-1]
    target = last_d - pd.DateOffset(months=months)
    earlier = s.loc[:target]
    if earlier.empty or (target - earlier.index[-1]).days > tolerance_days:
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


def gdp_momentum(s: pd.Series) -> tuple[float, float, float] | None:
    """(YoY now, YoY 2 quarters earlier, change) from QoQ SAAR prints; needs 6 gap-free quarters."""
    if len(s) < 6:
        return None
    q = s.groupby(s.index.to_period("Q")).last()
    if len(q) < 6:
        return None
    q = q.iloc[-6:]
    if (q.index[-1] - q.index[0]).n != 5:  # a missing quarter inside the window
        return None
    growth = (1 + q / 100) ** 0.25  # quarterly growth factor from an annualised rate

    def yoy(end: int) -> float:
        return float((growth.iloc[end - 3:end + 1].prod() - 1) * 100)
    now, before = yoy(5), yoy(3)
    return now, before, now - before


def state(score: float | None) -> str | None:
    if score is None:
        return None
    return "accelerating" if score >= FLAT else "decelerating" if score <= -FLAT else "flat"


def _signal(comps: list[dict]) -> dict:
    if not comps:
        return {"score": None, "direction": None, "state": None, "components": []}
    score = round(sum(c["score"] for c in comps) / len(comps), 2)
    return {"score": score, "direction": "up" if score > 0 else "down", "state": state(score), "components": comps}


def _freq(metrics: dict, mid: str, default: str) -> str:
    return (metrics.get(mid) or {}).get("frequency") or default


def growth_signal(metrics: dict[str, dict], today=None, stale: list | None = None) -> dict:
    stale = stale if stale is not None else []
    comps: list[dict] = []
    s = series(metrics, "indpro_yoy")
    if not s.empty and is_stale(s, _freq(metrics, "indpro_yoy", "monthly"), today):
        stale.append("indpro_yoy")
    elif (ip := change_over(s)):
        comps.append({"id": "indpro", "metric": "indpro", "label": "Industrial production YoY, 6m change",
                      "value": _r(ip[2]), "units": "pp", "asof": s.index[-1].strftime("%Y-%m-%d"),
                      "detail": {"now_pct": _r(ip[0]), "6m_ago_pct": _r(ip[1])},
                      "score": _r(_clip(ip[2] / 2.0))})
    s = series(metrics, "claims")
    if not s.empty and is_stale(s, _freq(metrics, "claims", "weekly"), today):
        stale.append("claims")
    elif (cl := claims_trend(s)):
        comps.append({"id": "claims", "metric": "claims", "label": "Initial claims, 4w vs 26w avg (inverted)",
                      "value": _r(cl[2] * 100, 1), "units": "%", "asof": s.index[-1].strftime("%Y-%m-%d"),
                      "detail": {"avg_4w_k": _r(cl[0], 1), "avg_26w_k": _r(cl[1], 1)},
                      "score": _r(_clip(-cl[2] / 0.10))})
    s = series(metrics, "gdp_qoq")
    if not s.empty and is_stale(s, _freq(metrics, "gdp_qoq", "quarterly"), today):
        stale.append("gdp_qoq")
    elif (g := gdp_momentum(s)):
        comps.append({"id": "gdp", "metric": "gdp", "label": "Real GDP YoY, 2-quarter change",
                      "value": _r(g[2]), "units": "pp", "asof": s.index[-1].strftime("%Y-%m-%d"),
                      "detail": {"yoy_now_pct": _r(g[0]), "yoy_2q_ago_pct": _r(g[1])},
                      "score": _r(_clip(g[2] / 1.0))})
    return _signal(comps)


def inflation_signal(metrics: dict[str, dict], today=None, stale: list | None = None) -> dict:
    stale = stale if stale is not None else []
    comps: list[dict] = []
    for mid, alias, label in (("core_cpi_yoy", "core_cpi", "Core CPI YoY, 6m change"),
                              ("core_pce_yoy", "core_pce", "Core PCE YoY, 6m change")):
        s = series(metrics, mid)
        if not s.empty and is_stale(s, _freq(metrics, mid, "monthly"), today):
            stale.append(mid)
            continue
        if (c := change_over(s)):
            comps.append({"id": mid, "metric": alias, "label": label, "value": _r(c[2]), "units": "pp",
                          "asof": s.index[-1].strftime("%Y-%m-%d"),
                          "detail": {"now_pct": _r(c[0]), "6m_ago_pct": _r(c[1])}, "score": _r(_clip(c[2] / 1.0))})
    return _signal(comps)


def quadrant_label(g: dict, i: dict) -> tuple[str | None, str | None, bool, list[str]]:
    """(quadrant by sign, display label, boundary?, quadrant names the text may use)."""
    if not g["direction"] or not i["direction"]:
        return None, None, False, []
    q = QUADRANTS[(g["direction"], i["direction"])]
    flip = {"up": "down", "down": "up"}
    g_flat, i_flat = g["state"] == "flat", i["state"] == "flat"
    if g_flat and i_flat:
        return q, "Near the centre: no clear growth or inflation momentum", True, list(QUADRANTS.values())
    if g_flat or i_flat:
        other = QUADRANTS[(flip[g["direction"]], i["direction"])] if g_flat else QUADRANTS[(g["direction"], flip[i["direction"]])]
        return q, f"{q} / {other} boundary", True, [q, other]
    return q, q, False, [q]


def growth_inflation(metrics: dict[str, dict], today=None, stale: list | None = None) -> dict:
    g, i = growth_signal(metrics, today, stale), inflation_signal(metrics, today, stale)
    q, label, boundary, allowed = quadrant_label(g, i)
    pce = (metrics.get("core_pce_yoy") or {}).get("value")
    note = None
    if pce is not None:
        note = (f"Quadrants describe the direction of change, not the level: core PCE inflation is "
                f"still {pce:.1f}% vs the {INFLATION_TARGET:.0f}% target.")
    return {"quadrant": q, "label": label, "boundary": boundary, "allowed_quadrants": allowed,
            "growth": g, "inflation": i, "level_note": note,
            "core_pce_pct": _r(pce, 1), "inflation_target_pct": INFLATION_TARGET}


def policy_stance(real_rate: float) -> str:
    lo, hi = NEUTRAL_BAND
    if real_rate > hi:
        return "restrictive"
    if real_rate < lo:
        return "accommodative"
    return "neutral"


def growth_policy(metrics: dict[str, dict], growth_direction: str | None, today=None,
                  stale: list | None = None) -> dict:
    stale = stale if stale is not None else []
    empty = {"label": None, "stance": None, "borderline": False, "real_rate_pct": None,
             "growth_direction": growth_direction, "neutral_band_pct": list(NEUTRAL_BAND), "note": R_STAR_NOTE}
    ff, pce = metrics.get("fed_funds"), metrics.get("core_pce_yoy")
    if not ff or not pce or ff.get("value") is None or pce.get("value") is None:
        return empty
    for mid, default in (("fed_funds", "daily"), ("core_pce_yoy", "monthly")):
        s = series(metrics, mid)
        if not s.empty and is_stale(s, _freq(metrics, mid, default), today):
            stale.append(mid)
            return empty
    upper, core = float(ff["value"]), float(pce["value"])
    mid = upper - 0.125
    real = mid - core                                   # unrounded: classification uses this
    stance = policy_stance(real)
    borderline = min(abs(real - NEUTRAL_BAND[0]), abs(real - NEUTRAL_BAND[1])) < POLICY_BORDERLINE
    growth_txt = {"up": ", growth rising", "down": ", growth slowing"}.get(growth_direction or "", "")
    return {"label": f"{stance.capitalize()} policy{growth_txt}", "stance": stance, "borderline": borderline,
            "real_rate_pct": _r(real), "fed_funds_upper_pct": _r(upper), "fed_funds_mid_pct": round(mid, 3),
            "core_pce_pct": _r(core), "neutral_band_pct": list(NEUTRAL_BAND),
            "growth_direction": growth_direction, "note": R_STAR_NOTE}


def _rows_by_ticker(markets: dict) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in (markets or {}).get("panels", {}).values():
        for g in p.get("groups", []):
            for r in g.get("rows", []):
                out.setdefault(r["ticker"], r)
    return out


def credit_duration(markets: dict, metrics: dict[str, dict] | None = None, period: str = "3M") -> dict:
    rows = _rows_by_ticker(markets)
    pairs = []
    for long, short in CREDIT_PAIRS:
        a = (rows.get(long) or {}).get("returns", {}).get(period)
        b = (rows.get(short) or {}).get("returns", {}).get(period)
        if a is None or b is None:
            continue
        a, b = round(float(a), 1), round(float(b), 1)
        pairs.append({"long": long, "short": short, "long_ret_pct": a, "short_ret_pct": b,
                      "spread_pp": round(a - b, 1)})
    oas = change_over(series(metrics or {}, "hy_oas"), months=3, tolerance_days=10)
    oas_bp = int(round(oas[2] * 100)) if oas else None
    out = {"label": None, "leader": None, "borderline": False, "score_pp": None, "period": period, "pairs": pairs,
           "hy_oas_3m_chg_bp": oas_bp, "hy_oas_confirms": None}
    if not pairs:
        return out
    score = round(sum(p["spread_pp"] for p in pairs) / len(pairs), 1)
    if score > CREDIT_DEADBAND:
        leader, label = "credit", "Credit leading duration"
    elif score < -CREDIT_DEADBAND:
        leader, label = "duration", "Duration leading credit"
    else:
        leader, label = "balanced", "Credit and duration balanced"
    confirms = None
    if oas_bp is not None and leader != "balanced":
        confirms = (oas_bp < 0) if leader == "credit" else (oas_bp > 0)
    out.update(label=label, leader=leader, score_pp=score, hy_oas_confirms=confirms,
               borderline=abs(abs(score) - CREDIT_DEADBAND) <= CREDIT_BORDERLINE)
    return out


def compute_regime(economy: dict | None, markets: dict | None, today=None) -> dict[str, Any]:
    metrics = {m["id"]: m for m in (economy or {}).get("metrics", [])}
    stale: list[str] = []
    gi = growth_inflation(metrics, today, stale)
    return {
        "growth_inflation": gi,
        "growth_policy": growth_policy(metrics, gi["growth"]["direction"], today, stale),
        "credit_duration": credit_duration(markets or {}, metrics),
        "stale_inputs": sorted(set(stale)),
    }
