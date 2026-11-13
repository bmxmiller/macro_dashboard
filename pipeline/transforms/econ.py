"""Transforms that turn raw economic series into display metrics."""
from __future__ import annotations

import math

import pandas as pd

YOY_PERIODS = {"monthly": 12, "quarterly": 4}


def to_regular(s: pd.Series, frequency: str) -> pd.Series:
    """Align observations to a regular period so pct_change(n) means what it says."""
    if frequency == "monthly":
        return s.groupby(s.index.to_period("M")).last().to_timestamp()
    if frequency == "quarterly":
        return s.groupby(s.index.to_period("Q")).last().to_timestamp()
    return s


def apply_transform(metric: dict, raw: dict[str, pd.Series]) -> pd.Series:
    t = metric["transform"]
    freq = metric.get("frequency", "monthly")
    if t == "ratio":
        num = to_regular(raw[metric["numerator"]], freq)
        den = to_regular(raw[metric["denominator"]], freq)
        out = (num / den).dropna() * metric.get("multiplier", 1)
    else:
        s = to_regular(raw[metric["series"]], freq)
        if t == "level":
            out = s
        elif t == "yoy":
            if freq not in YOY_PERIODS:
                raise ValueError(f"yoy needs monthly/quarterly data: {metric['id']}")
            out = s.pct_change(YOY_PERIODS[freq], fill_method=None) * 100
        elif t == "mom_pct":
            out = s.pct_change(1, fill_method=None) * 100
        elif t == "diff":
            out = s.diff(1)
        else:
            raise ValueError(f"unknown transform {t}")
    out = out * metric.get("scale", 1)
    return out.dropna()


def period_label(ts: pd.Timestamp, frequency: str) -> str:
    if frequency == "monthly":
        return ts.strftime("%b %Y").upper()
    if frequency == "quarterly":
        return f"Q{ts.quarter} {ts.year}"
    return ts.strftime("%d %b %Y").upper()


def zscore(s: pd.Series, years: int = 10) -> float | None:
    """Z-score of the latest value vs. its trailing `years` history."""
    s = s.dropna()
    if len(s) < 8:
        return None
    hist = s.loc[s.index[-1] - pd.DateOffset(years=years):]
    sd = hist.std()
    if not sd or math.isnan(sd):
        return None
    return round(float((s.iloc[-1] - hist.mean()) / sd), 2)


def percentile(s: pd.Series, years: int = 10) -> float | None:
    s = s.dropna()
    if len(s) < 8:
        return None
    hist = s.loc[s.index[-1] - pd.DateOffset(years=years):]
    return round(float((hist <= s.iloc[-1]).mean() * 100), 0)


def history(s: pd.Series, years: int = 25, max_points: int = 600) -> list[list]:
    s = s.dropna().loc[lambda x: x.index >= x.index[-1] - pd.DateOffset(years=years)]
    if len(s) > max_points:  # downsample daily series to weekly
        s = s.resample("W").last().dropna()
    return [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in s.items()]
