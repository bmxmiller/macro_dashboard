"""Upcoming earnings dates and EPS estimates from Yahoo Finance via yfinance (free, no key).

yfinance does its own HTTP (like fetchers/yahoo.py). One request per ticker,
run sequentially with a small pause to stay polite.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def quote_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}"


def time_of_day(ts: pd.Timestamp) -> str | None:
    """Classify a US/Eastern report timestamp: BMO (before 9:30), AMC (16:00+), DMH (during), None (unknown)."""
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York")
    mins = ts.hour * 60 + ts.minute
    if mins == 0:
        return None  # midnight = time not announced
    if mins < 9 * 60 + 30:
        return "BMO"
    if mins >= 16 * 60:
        return "AMC"
    return "DMH"


def _f(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else round(f, 4)


def parse_earnings_dates(df: pd.DataFrame, today: date, days: int) -> dict | None:
    """From yfinance get_earnings_dates() output, pick the next report within `days`.

    Returns {date, time, eps_estimate, eps_prior_year, prior_year_date} or None.
    The prior-year EPS is the reported EPS of the report 300–430 days earlier.
    """
    if df is None or df.empty:
        return None
    idx = pd.DatetimeIndex(df.index)
    local = idx.tz_convert("America/New_York") if idx.tz is not None else idx
    rows = list(zip(local, df.to_dict("records")))
    end = today + timedelta(days=days)
    upcoming = sorted((r for r in rows if today <= r[0].date() <= end), key=lambda r: r[0])
    if not upcoming:
        return None
    ts, rec = upcoming[0]
    prior = [(t, r) for t, r in rows
             if timedelta(days=300) <= ts - t <= timedelta(days=430) and _f(r.get("Reported EPS")) is not None]
    prior.sort(key=lambda x: abs((ts - x[0]).days - 365))
    return {
        "date": ts.date().isoformat(),
        "time": time_of_day(ts),
        "eps_estimate": _f(rec.get("EPS Estimate")),
        "eps_prior_year": _f(prior[0][1].get("Reported EPS")) if prior else None,
        "prior_year_date": prior[0][0].date().isoformat() if prior else None,
    }


def parse_calendar(cal: dict, today: date, days: int) -> dict | None:
    """Fallback using Ticker.calendar (date only, no time-of-day or prior-year EPS)."""
    dates = [d for d in (cal or {}).get("Earnings Date") or [] if isinstance(d, date)]
    nxt = sorted(d for d in dates if today <= d <= today + timedelta(days=days))
    if not nxt:
        return None
    return {"date": nxt[0].isoformat(), "time": None, "eps_estimate": _f(cal.get("Earnings Average")),
            "eps_prior_year": None, "prior_year_date": None}


def fetch_one(ticker: str, today: date, days: int) -> dict | None:
    tk = yf.Ticker(ticker)
    try:
        df = tk.get_earnings_dates(limit=12)
        if df is not None and not df.empty:
            return parse_earnings_dates(df, today, days)
    except Exception as e:  # noqa: BLE001 - fall back to calendar
        log.info("earnings_dates %s failed (%s); trying calendar", ticker, e)
    # Only when the main call failed or came back empty (one extra request)
    return parse_calendar(tk.calendar, today, days)


def fetch_upcoming(companies: list[dict], days: int = 14, pause: float = 0.4) -> tuple[list[dict], list[str]]:
    today = date.today()
    items, failed = [], []
    for c in companies:
        t = c["t"]
        try:
            res = fetch_one(t, today, days)
        except Exception as e:  # noqa: BLE001 - isolate per-ticker failures
            log.warning("earnings %s failed: %s", t, e)
            failed.append(t)
            res = None
        if res:
            items.append({"ticker": t, "name": c["name"], **res, "source_url": quote_url(t)})
        time.sleep(pause)
    items.sort(key=lambda x: (x["date"], {"BMO": 0, "DMH": 1, "AMC": 2}.get(x["time"] or "", 3), x["ticker"]))
    return items, failed
