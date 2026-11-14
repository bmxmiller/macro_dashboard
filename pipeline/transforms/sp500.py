"""Pure helpers for the S&P 500 heat map (no I/O, unit-tested offline)."""
from __future__ import annotations

import math

import pandas as pd

from .returns import period_returns, value_on_or_before


def market_cap_bn(shares: float | None, price: float | None) -> float | None:
    """Market capitalisation in US$ billions = shares outstanding x last close."""
    if shares is None or price is None:
        return None
    if not (math.isfinite(shares) and math.isfinite(price)) or shares <= 0 or price <= 0:
        return None
    return round(shares * price / 1e9, 2)


def stale_share_tickers(prev_prices: dict[str, float], prev_asof: str | None, close: pd.DataFrame,
                        tol: float = 0.05) -> list[str]:
    """Tickers whose cached share count is probably out of date because of a stock split.

    Closes are split-adjusted, so after a split the history is rescaled: yesterday's close in
    the NEW download no longer matches the price we published for that day. A mismatch beyond
    `tol` means the cached share count (which was not split-adjusted) must be refetched now
    instead of waiting for the weekly refresh. Ordinary price revisions are far below 5%.
    """
    if not prev_asof:
        return []
    when = pd.Timestamp(prev_asof)
    out: list[str] = []
    for t, old in prev_prices.items():
        if t not in close or not old:
            continue
        new = value_on_or_before(close[t].dropna(), when)
        if new and abs(old / new - 1) > tol:
            out.append(t)
    return out


def build_rows(companies: list[dict], close: pd.DataFrame, shares: dict[str, float]) -> tuple[list[dict], list[str]]:
    """One row per constituent with a price and a market cap.

    Returns (rows, failed). A company with no price history, no share count (so no market cap
    and nothing to size its rectangle by), or whose last price is older than the latest date in
    the download (halted, or a Yahoo gap: its 1D return and cap would be from a different day)
    is listed in `failed` and left out. Returns are PRICE returns on unadjusted (split-adjusted) closes.
    """
    latest = close.dropna(how="all").index[-1] if not close.dropna(how="all").empty else None
    rows: list[dict] = []
    failed: list[str] = []
    for c in companies:
        t = c["t"]
        s = close[t].dropna() if t in close else pd.Series(dtype=float)
        if s.empty or s.index[-1] != latest:
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
