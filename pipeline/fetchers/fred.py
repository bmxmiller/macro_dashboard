"""FRED (Federal Reserve Bank of St. Louis) data.

Uses the official API when FRED_API_KEY is set, otherwise falls back to the
public no-key CSV download endpoint (fredgraph.csv). Both are free.
"""
from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import pandas as pd

from .http import get

API = "https://api.stlouisfed.org/fred"
CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv"


def api_key() -> str | None:
    return os.environ.get("FRED_API_KEY") or None


def series_url(series_id: str) -> str:
    return f"https://fred.stlouisfed.org/series/{series_id}"


def fetch_series(series_id: str, start: str | date = "2000-01-01") -> pd.Series:
    """Return a float Series indexed by date (NaNs dropped)."""
    start = str(start)
    key = api_key()
    if key:
        r = get(f"{API}/series/observations", params={
            "series_id": series_id, "api_key": key, "file_type": "json", "observation_start": start,
        })
        obs = r.json()["observations"]
        s = pd.Series({o["date"]: o["value"] for o in obs}, dtype="object")
    else:
        # Keyless fallback: fine for a handful of series, but FRED throttles bulk use.
        r = get(CSV, params={"id": series_id, "cosd": start}, timeout=20)
        df = pd.read_csv(io.StringIO(r.text))
        s = pd.Series(df.iloc[:, 1].values, index=df.iloc[:, 0].values, dtype="object")
    s.index = pd.to_datetime(s.index)
    s = pd.to_numeric(s.replace(".", None), errors="coerce").dropna().astype(float)
    s.name = series_id
    return s


def fetch_many(series_ids: list[str], start: str = "2000-01-01", workers: int = 6) -> dict[str, pd.Series]:
    """Fetch several series concurrently. Failures are returned as exceptions, not raised."""
    ids = sorted(set(series_ids))
    out: dict[str, pd.Series | Exception] = {}
    if not api_key():
        workers = 1  # be gentle with the public CSV endpoint

    def one(sid: str):
        try:
            return sid, fetch_series(sid, start)
        except Exception as e:  # noqa: BLE001 - isolate per-series failures
            return sid, e

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for sid, res in ex.map(one, ids):
            out[sid] = res
    return out


# ── Release calendar (API key required) ────────────────────────────────────

def release_for_series(series_id: str) -> dict | None:
    key = api_key()
    if not key:
        return None
    r = get(f"{API}/series/release", params={"series_id": series_id, "api_key": key, "file_type": "json"})
    rel = r.json().get("releases", [])
    return rel[0] if rel else None


def upcoming_release_dates(days_ahead: int = 45) -> list[dict]:
    """All FRED release dates from today to +days_ahead (includes not-yet-published dates)."""
    key = api_key()
    if not key:
        return []
    today = date.today()
    r = get(f"{API}/releases/dates", params={
        "api_key": key, "file_type": "json",
        "realtime_start": today.isoformat(),
        "realtime_end": (today + timedelta(days=days_ahead)).isoformat(),
        "include_release_dates_with_no_data": "true",
        "sort_order": "asc", "limit": 1000,
    })
    return r.json().get("release_dates", [])
