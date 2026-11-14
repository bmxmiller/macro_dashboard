import math

import pandas as pd
import yaml

from pipeline.schemas import SP500, SP500Row
from pipeline.transforms import sp500


def _close():
    idx = pd.bdate_range("2026-10-01", periods=40)
    return pd.DataFrame({
        "AAA": [100.0 + i for i in range(40)],            # rises to 139
        "BBB": [50.0] * 40,                               # flat
        "CCC": [float("nan")] * 40,                       # no price history
    }, index=idx)


COMPANIES = [
    {"t": "AAA", "name": "Alpha", "sector": "Technology"},
    {"t": "BBB", "name": "Beta", "sector": "Energy"},
    {"t": "CCC", "name": "Gamma", "sector": "Energy"},
    {"t": "DDD", "name": "Delta", "sector": "Utilities"},   # not in the download at all
]


def test_market_cap_bn():
    assert sp500.market_cap_bn(15e9, 200.0) == 3000.0
    assert sp500.market_cap_bn(None, 10.0) is None
    assert sp500.market_cap_bn(10.0, None) is None
    assert sp500.market_cap_bn(0, 10.0) is None
    assert sp500.market_cap_bn(10.0, -1.0) is None
    assert sp500.market_cap_bn(float("nan"), 10.0) is None
    assert sp500.market_cap_bn(1e9, math.inf) is None


def test_build_rows_sorted_by_cap_and_failures_listed():
    shares = {"AAA": 1e9, "BBB": 4e9, "CCC": 1e9}   # DDD has no shares and no prices
    rows, failed = sp500.build_rows(COMPANIES, _close(), shares)
    assert [r["t"] for r in rows] == ["AAA", "BBB"] or [r["t"] for r in rows] == ["BBB", "AAA"]
    assert rows[0]["cap"] >= rows[1]["cap"]
    by = {r["t"]: r for r in rows}
    assert by["AAA"]["cap"] == 139.0 and by["BBB"]["cap"] == 200.0
    assert rows[0]["t"] == "BBB"
    assert failed == ["CCC", "DDD"]


def test_build_rows_drops_company_without_share_count():
    rows, failed = sp500.build_rows(COMPANIES[:2], _close(), {"AAA": 1e9})
    assert [r["t"] for r in rows] == ["AAA"]
    assert failed == ["BBB"]


def test_build_rows_returns_are_price_returns_in_percent():
    rows, _ = sp500.build_rows(COMPANIES[:2], _close(), {"AAA": 1e9, "BBB": 1e9})
    aaa = next(r for r in rows if r["t"] == "AAA")
    assert aaa["returns"]["1D"] == round((139 / 138 - 1) * 100, 2)
    assert aaa["returns"]["3Y"] is None          # history too short: None, not 0
    bbb = next(r for r in rows if r["t"] == "BBB")
    assert bbb["returns"]["1W"] == 0.0


def test_rows_validate_against_schema():
    rows, failed = sp500.build_rows(COMPANIES, _close(), {"AAA": 1e9, "BBB": 1e9})
    model = SP500(generated_at="x", asof="2026-11-25", periods=["1D"], source_url="https://x.test",
                  about={"what": "a", "why": "b", "how_to_read": "c"}, failed=failed,
                  rows=[SP500Row(**r) for r in rows])
    assert len(model.rows) == 2


def test_registry_is_well_formed():
    from pipeline.build import REGISTRY
    reg = yaml.safe_load((REGISTRY / "sp500.yaml").read_text(encoding="utf-8"))
    comps = reg["companies"]
    tickers = [c["t"] for c in comps]
    assert 490 <= len(tickers) <= 520
    assert len(tickers) == len(set(tickers)), "duplicate ticker"
    assert all(set(c) == {"t", "name", "sector"} for c in comps)
    assert not any("." in t for t in tickers), "Yahoo tickers use '-' (BRK-B), not '.'"
    assert {c["sector"] for c in comps} == {
        "Communication Services", "Consumer Discretionary", "Consumer Staples", "Energy", "Financials",
        "Health Care", "Industrials", "Information Technology", "Materials", "Real Estate", "Utilities"}
    assert set(reg["about"]) == {"what", "why", "how_to_read"}
