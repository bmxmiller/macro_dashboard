"""Yahoo Finance prices via yfinance (free, no key).

We download unadjusted Close, Adj Close (dividend-adjusted → total return) and
Dividends in one batch call.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass
class PriceData:
    close: pd.DataFrame       # unadjusted closes (display price)
    adj_close: pd.DataFrame   # total-return series
    dividends: pd.DataFrame


def quote_url(ticker: str) -> str:
    return f"https://finance.yahoo.com/quote/{ticker}"


def fetch_prices(tickers: list[str], period: str = "3y") -> PriceData:
    tickers = sorted(set(tickers))
    raw = yf.download(
        tickers, period=period, interval="1d", auto_adjust=False, actions=True,
        group_by="column", progress=False, threads=True,
    )
    if raw is None or raw.empty:
        raise RuntimeError("yfinance returned no data")

    def field(name: str) -> pd.DataFrame:
        if name not in raw.columns.get_level_values(0):
            return pd.DataFrame(index=raw.index, columns=tickers, dtype=float)
        df = raw[name]
        if isinstance(df, pd.Series):  # single ticker
            df = df.to_frame(tickers[0])
        return df.reindex(columns=tickers)

    close = field("Close")
    adj = field("Adj Close")
    adj = adj.fillna(close)  # FX / futures have no adjustments
    divs = field("Dividends").fillna(0.0)
    close.index = adj.index = divs.index = pd.to_datetime(close.index).tz_localize(None)
    return PriceData(close=close, adj_close=adj, dividends=divs)
