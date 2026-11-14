"""S&P 500 constituent prices and share counts from Yahoo Finance via yfinance (free, no key).

Prices come in chunked batch downloads (500 tickers in one call is unreliable); share
counts are one request per ticker, so build.py only refreshes them weekly and reuses
the cached values from the previous sp500.json in between.
"""
from __future__ import annotations

import logging
import time

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def quote_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}"


def fetch_closes(tickers: list[str], period: str = "4y", chunk_size: int = 100, retries: int = 2) -> pd.DataFrame:
    """Unadjusted (split-adjusted, dividend-excluded) daily closes, one column per ticker."""
    tickers = sorted(set(tickers))
    frames: list[pd.DataFrame] = []
    for i in range(0, len(tickers), chunk_size):
        chunk = tickers[i:i + chunk_size]
        df = None
        for attempt in range(retries + 1):
            try:
                raw = yf.download(chunk, period=period, interval="1d", auto_adjust=False, actions=False,
                                  group_by="column", progress=False, threads=True)
                if raw is not None and not raw.empty and "Close" in raw.columns.get_level_values(0):
                    df = raw["Close"]
                    if isinstance(df, pd.Series):
                        df = df.to_frame(chunk[0])
                    break
            except Exception as e:  # noqa: BLE001 - yfinance raises assorted errors; retry then move on
                log.warning("chunk %d attempt %d failed: %s", i // chunk_size, attempt + 1, e)
            time.sleep(2 * (attempt + 1))
        if df is None:
            log.warning("chunk %d (%d tickers) returned nothing", i // chunk_size, len(chunk))
            continue
        frames.append(df)
    if not frames:
        raise RuntimeError("yfinance returned no data for any S&P 500 chunk")
    close = pd.concat(frames, axis=1)
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return close.reindex(columns=tickers)


def fetch_shares(tickers: list[str], throttle: float = 0.3) -> dict[str, float]:
    """Shares outstanding per ticker (one request each). Tickers that fail are left out."""
    out: dict[str, float] = {}
    for t in tickers:
        try:
            v = yf.Ticker(t).fast_info["shares"]
            if v and float(v) > 0:
                out[t] = float(v)
        except Exception as e:  # noqa: BLE001
            log.debug("shares for %s failed: %s", t, e)
        time.sleep(throttle)
    return out
