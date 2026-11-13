"""Period returns for price series.

All returns use point-in-time "last observation on or before" lookups, so
weekends/holidays and different trading calendars (futures, FX, crypto) are
handled consistently.
"""
from __future__ import annotations

import math

import pandas as pd

PERIODS = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"]


def _anchor_date(asof: pd.Timestamp, period: str) -> pd.Timestamp:
    if period == "1W":
        return asof - pd.Timedelta(days=7)
    if period == "1M":
        return asof - pd.DateOffset(months=1)
    if period == "3M":
        return asof - pd.DateOffset(months=3)
    if period == "6M":
        return asof - pd.DateOffset(months=6)
    if period == "YTD":
        return pd.Timestamp(year=asof.year, month=1, day=1) - pd.Timedelta(days=1)
    if period == "1Y":
        return asof - pd.DateOffset(years=1)
    if period == "3Y":
        return asof - pd.DateOffset(years=3)
    raise ValueError(period)


def value_on_or_before(s: pd.Series, when: pd.Timestamp) -> float | None:
    sub = s.loc[:when]
    if sub.empty:
        return None
    return float(sub.iloc[-1])


def period_returns(s: pd.Series, mode: str = "pct") -> dict[str, float | None]:
    """mode='pct' → % total return; mode='diff' → absolute change (e.g. yields in pp)."""
    s = s.dropna()
    out: dict[str, float | None] = {p: None for p in PERIODS}
    if len(s) < 2:
        return out
    asof = s.index[-1]
    last = float(s.iloc[-1])

    def calc(base: float | None) -> float | None:
        if base is None or (mode == "pct" and base == 0):
            return None
        v = (last - base) if mode == "diff" else (last / base - 1) * 100
        return None if math.isnan(v) else round(v, 4)

    out["1D"] = calc(float(s.iloc[-2]))
    first_date = s.index[0]
    for p in PERIODS[1:]:
        anchor = _anchor_date(asof, p)
        # don't report a period the history doesn't cover (allow 5-day slack)
        if anchor < first_date - pd.Timedelta(days=5):
            continue
        out[p] = calc(value_on_or_before(s, anchor))
    return out


def sparkline(s: pd.Series, months: int = 12, points: int = 52) -> list[float]:
    s = s.dropna()
    if s.empty:
        return []
    s = s.loc[s.index[-1] - pd.DateOffset(months=months):]
    if len(s) > points:
        step = len(s) / points
        idx = [int(i * step) for i in range(points - 1)] + [len(s) - 1]
        s = s.iloc[idx]
    return [round(float(v), 6) for v in s.values]


def trailing_yield(close: pd.Series, dividends: pd.Series) -> float | None:
    """Trailing-12-month distribution yield in % (distributions / latest price)."""
    close = close.dropna()
    if close.empty:
        return None
    asof = close.index[-1]
    d = dividends.loc[asof - pd.DateOffset(years=1):asof].sum()
    if d <= 0:
        return None
    return round(float(d) / float(close.iloc[-1]) * 100, 2)
