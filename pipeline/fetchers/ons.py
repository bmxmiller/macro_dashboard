"""UK Office for National Statistics time series (free, no key).

Each ONS time series has a JSON endpoint at ``https://www.ons.gov.uk<uri>/data``,
where ``uri`` is e.g. ``/economy/inflationandpriceindices/timeseries/d7g7/mm23``.
"""
from __future__ import annotations

import pandas as pd

from .http import get

BASE = "https://www.ons.gov.uk"
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}


def series_url(uri: str) -> str:
    return BASE + uri


def _parse_date(label: str) -> pd.Timestamp | None:
    """'2026 SEP' -> 2026-09-01, '2026 Q2' -> 2026-04-01, '2026' -> 2026-01-01."""
    parts = label.strip().upper().split()
    try:
        year = int(parts[0])
        if len(parts) == 1:
            return pd.Timestamp(year, 1, 1)
        p = parts[1]
        if p.startswith("Q"):
            return pd.Timestamp(year, 3 * (int(p[1:]) - 1) + 1, 1)
        return pd.Timestamp(year, MONTHS[p[:3]], 1)
    except (ValueError, KeyError, IndexError):
        return None


def parse_timeseries(payload: dict, frequency: str) -> pd.Series:
    """Pick the months/quarters/years block matching `frequency` and return a float Series."""
    key = {"monthly": "months", "quarterly": "quarters", "annual": "years"}[frequency]
    obs = payload.get(key) or []
    data = {}
    for o in obs:
        d = _parse_date(str(o.get("date", "")))
        try:
            v = float(o.get("value"))
        except (TypeError, ValueError):
            continue
        if d is not None:
            data[d] = v
    s = pd.Series(data, dtype=float).sort_index()
    if s.empty:
        raise ValueError(f"ONS series has no {key} observations")
    return s


def merge_vintages(series: list[pd.Series]) -> pd.Series:
    """Combine the same CDID from several ONS datasets (e.g. QNA and the newer PN2 first
    estimate). The series that ends latest wins on overlapping dates; older ones fill gaps."""
    ordered = sorted((s for s in series if not s.empty), key=lambda s: s.index[-1], reverse=True)
    if not ordered:
        raise ValueError("no ONS data")
    out = ordered[0]
    for s in ordered[1:]:
        out = out.combine_first(s)
    return out.sort_index()


def fetch_series(uri: str, frequency: str, alt_uris: list[str] | None = None) -> pd.Series:
    """Fetch `uri` (and optionally the same series in other datasets), merged by vintage."""
    parts, errors = [], []
    for u in [uri, *(alt_uris or [])]:
        try:
            parts.append(parse_timeseries(get(series_url(u) + "/data", timeout=30).json(), frequency))
        except Exception as e:  # noqa: BLE001 - one dataset failing is fine
            errors.append(f"{u}: {e}")
    if not parts:
        raise RuntimeError("; ".join(errors))
    return merge_vintages(parts)
