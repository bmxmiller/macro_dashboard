"""CFTC Commitments of Traders via the free Socrata API (publicreporting.cftc.gov, no key).

Two futures-only reports are used:
* ``tff`` (Traders in Financial Futures, dataset gpe5-46if) for equity index,
  rates, FX and bitcoin futures; the speculative group is *Leveraged Funds*.
* ``disaggregated`` (dataset 72hh-3qpy) for physical commodities; the
  speculative group is *Managed Money*.
Positions are as of Tuesday and published the following Friday at 3:30 pm ET.
"""
from __future__ import annotations

import pandas as pd

from .http import get

API = "https://publicreporting.cftc.gov/resource/{ds}.json"
COT_PAGE = "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm"

REPORTS = {
    "tff": {
        "dataset": "gpe5-46if", "group": "Leveraged funds", "report": "Traders in Financial Futures (futures only)",
        "long": "lev_money_positions_long", "short": "lev_money_positions_short",
    },
    "disaggregated": {
        "dataset": "72hh-3qpy", "group": "Managed money", "report": "Disaggregated (futures only)",
        "long": "m_money_positions_long_all", "short": "m_money_positions_short_all",
    },
}
DATE = "report_date_as_yyyy_mm_dd"


def dataset_url(report: str) -> str:
    return f"https://publicreporting.cftc.gov/d/{REPORTS[report]['dataset']}"


def fetch_rows(code: str, report: str, since: str) -> list[dict]:
    cfg = REPORTS[report]
    r = get(API.format(ds=cfg["dataset"]), params={
        "$select": f"{DATE},market_and_exchange_names,open_interest_all,{cfg['long']},{cfg['short']}",
        "$where": f"cftc_contract_market_code='{code}' AND {DATE} >= '{since}T00:00:00'",
        "$order": f"{DATE} ASC",
        "$limit": 2000,
    }, timeout=45)
    return r.json()


def parse_rows(rows: list[dict], report: str) -> pd.DataFrame:
    """Socrata rows -> DataFrame[date] with long, short, oi, net (all floats), sorted, deduped."""
    cfg = REPORTS[report]
    recs = []
    for r in rows:
        try:
            recs.append({
                "date": pd.Timestamp(str(r[DATE])[:10]),
                "long": float(r[cfg["long"]]),
                "short": float(r[cfg["short"]]),
                "oi": float(r.get("open_interest_all") or "nan"),
            })
        except (KeyError, TypeError, ValueError):
            continue
    if not recs:
        raise ValueError("no usable COT rows")
    df = pd.DataFrame(recs).drop_duplicates("date", keep="last").set_index("date").sort_index()
    df["net"] = df["long"] - df["short"]
    return df


def summarize(df: pd.DataFrame, years: int = 3) -> dict:
    """Latest net position, week-over-week change and its rank within the trailing window."""
    last_d = df.index[-1]
    win = df.loc[last_d - pd.DateOffset(years=years):]
    net = win["net"]
    cur = float(net.iloc[-1])
    prev = float(df["net"].iloc[-2]) if len(df) > 1 else None
    lo, hi = float(net.min()), float(net.max())
    oi = float(df["oi"].iloc[-1])
    return {
        "report_date": last_d.strftime("%Y-%m-%d"),
        "long": int(df["long"].iloc[-1]),
        "short": int(df["short"].iloc[-1]),
        "net": int(cur),
        "net_prev": int(prev) if prev is not None else None,
        "change_wow": int(cur - prev) if prev is not None else None,
        "open_interest": int(oi) if oi == oi else None,
        "net_pct_oi": round(cur / oi * 100, 1) if oi and oi == oi else None,
        "percentile_3y": round(float((net <= cur).mean() * 100), 0) if len(net) >= 8 else None,
        "cot_index_3y": round((cur - lo) / (hi - lo) * 100, 0) if hi > lo else None,
        "min_3y": int(lo), "max_3y": int(hi),
        "weeks": int(len(net)),
        "history": [[d.strftime("%Y-%m-%d"), int(v)] for d, v in net.items()],
    }
