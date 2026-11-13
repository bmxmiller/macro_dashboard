"""CNN Business Fear & Greed Index (public JSON used by cnn.com, no key).

The endpoint answers 418 to non-browser clients, so this one request sends
browser-like headers. The global session User-Agent is left untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .http import browser_headers, get

URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
PAGE = "https://www.cnn.com/markets/fear-and-greed"

COMPONENTS = [  # (json key, display name)
    ("market_momentum_sp500", "Market Momentum"),
    ("stock_price_strength", "Stock Price Strength"),
    ("stock_price_breadth", "Stock Price Breadth"),
    ("put_call_options", "Put/Call Options"),
    ("market_volatility_vix", "Market Volatility"),
    ("junk_bond_demand", "Junk Bond Demand"),
    ("safe_haven_demand", "Safe Haven Demand"),
]


def _num(v, nd: int = 1):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, nd)


def _ms_to_date(ms) -> str | None:
    try:
        return datetime.fromtimestamp(float(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return None


def parse(payload: dict) -> dict:
    """Normalise CNN's graphdata JSON. Raises ValueError if the headline score is missing."""
    fg = payload.get("fear_and_greed") or {}
    score = _num(fg.get("score"))
    if score is None:
        raise ValueError("Fear & Greed payload has no score")
    hist_raw = (payload.get("fear_and_greed_historical") or {}).get("data") or []
    history, seen = [], set()
    for p in hist_raw:
        d, y = _ms_to_date(p.get("x")), _num(p.get("y"))
        if d and y is not None:
            if d in seen:
                history[-1] = [d, y]
            else:
                seen.add(d)
                history.append([d, y])
    comps = []
    for key, name in COMPONENTS:
        c = payload.get(key)
        if not isinstance(c, dict) or _num(c.get("score")) is None:
            continue
        data = c.get("data") or []
        last = data[-1] if data else {}
        comps.append({
            "id": key, "name": name,
            "score": _num(c.get("score")),
            "rating": str(c.get("rating") or "") or None,
            "value": _num(last.get("y"), 4) if last else None,
            "asof": _ms_to_date(c.get("timestamp")),
        })
    return {
        "score": score,
        "rating": str(fg.get("rating") or "") or None,
        "asof": str(fg.get("timestamp") or "") or None,
        "previous_close": _num(fg.get("previous_close")),
        "previous_1_week": _num(fg.get("previous_1_week")),
        "previous_1_month": _num(fg.get("previous_1_month")),
        "previous_1_year": _num(fg.get("previous_1_year")),
        "history": history,
        "components": comps,
        "source_url": PAGE,
    }


def fetch() -> dict:
    r = get(URL, headers=browser_headers(
        Accept="application/json, text/plain, */*",
        Referer="https://www.cnn.com/", Origin="https://www.cnn.com",
    ), timeout=30)
    return parse(r.json())
