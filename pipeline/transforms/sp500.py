"""Pure helpers for the S&P 500 heat map (no I/O, unit-tested offline)."""
from __future__ import annotations

import math

import pandas as pd

from .returns import period_returns


def market_cap_bn(shares: float | None, price: float | None) -> float | None:
    """Market capitalisation in US$ billions = shares outstanding x last close."""
    if shares is None or price is None:
        return None
    if not (math.isfinite(shares) and math.isfinite(price)) or shares <= 0 or price <= 0:
        return None
    return round(shares * price / 1e9, 2)


def build_rows(companies: list[dict], close: pd.DataFrame, shares: dict[str, float]) -> tuple[list[dict], list[str]]:
    """One row per constituent with a price and a market cap.

    Returns (rows, failed). A company with no price history, or no share count (so no
    market cap and nothing to size its rectangle by), is listed in `failed` and left out.
    Returns are PRICE returns on unadjusted (split-adjusted) closes.
    """
    rows: list[dict] = []
    failed: list[str] = []
    for c in companies:
        t = c["t"]
        s = close[t].dropna() if t in close else pd.Series(dtype=float)
        if s.empty:
            failed.append(t)
            continue
        price = float(s.iloc[-1])
        cap = market_cap_bn(shares.get(t), price)
        if cap is None:
            failed.append(t)
            continue
        rows.append({
            "t": t, "name": c["name"], "sector": c["sector"],
            "price": round(price, 2), "shares": int(shares[t]), "cap": cap,
            "returns": {k: (None if v is None else round(v, 2)) for k, v in period_returns(s, mode="pct").items()},
        })
    rows.sort(key=lambda r: r["cap"], reverse=True)
    return rows, failed
