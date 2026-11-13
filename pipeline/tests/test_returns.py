"""Tests for pipeline.transforms.returns (pure, offline)."""
from __future__ import annotations

import pandas as pd
import pytest

from pipeline.transforms.returns import PERIODS, period_returns, sparkline, trailing_yield, value_on_or_before


def bdays(start: str, end: str, value_fn=None) -> pd.Series:
    idx = pd.bdate_range(start, end)
    vals = [value_fn(i, d) if value_fn else 100.0 + i for i, d in enumerate(idx)]
    return pd.Series(vals, index=idx, dtype=float)


def test_periods_constant():
    assert PERIODS == ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"]


def test_value_on_or_before_uses_last_prior_obs():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-02", "2026-01-09"]))
    assert value_on_or_before(s, pd.Timestamp("2026-01-08")) == 1.0
    assert value_on_or_before(s, pd.Timestamp("2026-01-09")) == 2.0
    assert value_on_or_before(s, pd.Timestamp("2026-01-01")) is None


def test_1d_pct_and_diff():
    s = pd.Series([100.0, 110.0], index=pd.to_datetime(["2026-03-02", "2026-03-03"]))
    assert period_returns(s)["1D"] == pytest.approx(10.0)
    assert period_returns(s, mode="diff")["1D"] == pytest.approx(10.0)
    y = pd.Series([4.25, 4.10], index=s.index)
    assert period_returns(y, mode="diff")["1D"] == pytest.approx(-0.15)


def test_1d_uses_previous_observation_across_weekend():
    # Friday -> Monday: 1D is vs. Friday's close.
    s = pd.Series([50.0, 55.0], index=pd.to_datetime(["2026-03-06", "2026-03-09"]))
    assert period_returns(s)["1D"] == pytest.approx(10.0)


def test_1w_anchors_on_last_obs_on_or_before_holiday():
    # asof Mon 2026-03-16 -> anchor Mon 2026-03-09, a holiday here (missing),
    # so the base is Fri 2026-03-06.
    idx = pd.to_datetime(["2026-03-05", "2026-03-06", "2026-03-10", "2026-03-16"])
    s = pd.Series([90.0, 100.0, 105.0, 120.0], index=idx)
    assert period_returns(s)["1W"] == pytest.approx(20.0)


def test_1m_anchor_on_weekend_uses_friday():
    # asof Wed 2026-11-18 -> anchor Sun 2026-10-18 -> base is Fri 2026-10-16.
    idx = pd.to_datetime(["2026-10-15", "2026-10-16", "2026-10-19", "2026-11-18"])
    s = pd.Series([1.0, 100.0, 1.0, 110.0], index=idx)
    assert period_returns(s)["1M"] == pytest.approx(10.0)


def test_ytd_anchor_is_last_close_of_prior_year():
    s = bdays("2025-12-01", "2026-02-27", lambda i, d: 200.0 if d == pd.Timestamp("2025-12-31") else 100.0)
    s.iloc[-1] = 220.0
    assert period_returns(s)["YTD"] == pytest.approx(10.0)


def test_ytd_anchor_when_dec_31_is_not_a_trading_day():
    # No Dec 31 obs -> base must be Dec 30, never a January value.
    s = pd.Series(
        [80.0, 90.0, 150.0, 99.0],
        index=pd.to_datetime(["2025-12-29", "2025-12-30", "2026-01-02", "2026-01-05"]),
    )
    assert period_returns(s)["YTD"] == pytest.approx(10.0)


def test_pct_returns_on_flat_history():
    s = bdays("2022-01-03", "2026-11-13", lambda i, d: 100.0)
    s.iloc[-1] = 150.0
    r = period_returns(s)
    for p in PERIODS:
        assert r[p] == pytest.approx(50.0), p


def test_diff_mode_is_absolute_change():
    s = bdays("2025-01-01", "2026-11-13", lambda i, d: 4.0)
    s.iloc[-1] = 3.5
    r = period_returns(s, mode="diff")
    assert r["1M"] == pytest.approx(-0.5)
    assert r["1Y"] == pytest.approx(-0.5)
    assert r["3Y"] is None


def test_insufficient_history_returns_none():
    s = bdays("2026-06-01", "2026-11-13")
    r = period_returns(s)
    assert r["1D"] is not None and r["1M"] is not None and r["3M"] is not None
    # 6M anchor 2026-05-13 is more than 5 days before the first obs
    assert r["6M"] is None
    assert r["1Y"] is None and r["3Y"] is None


def test_within_slack_but_no_prior_obs_is_none():
    # First obs 2026-10-16 is within the 5-day slack of the 1M anchor 2026-10-13,
    # but there is no obs on/before the anchor, so no base exists.
    s = bdays("2026-10-16", "2026-11-13")
    assert period_returns(s)["1M"] is None


def test_too_short_or_nan_series():
    assert all(v is None for v in period_returns(pd.Series(dtype=float)).values())
    one = pd.Series([1.0], index=pd.to_datetime(["2026-01-02"]))
    assert all(v is None for v in period_returns(one).values())
    s = pd.Series([1.0, float("nan"), 2.0], index=pd.to_datetime(["2026-01-02", "2026-01-05", "2026-01-06"]))
    assert period_returns(s)["1D"] == pytest.approx(100.0)


def test_pct_zero_base_is_none():
    s = pd.Series([0.0, 1.0], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    assert period_returns(s)["1D"] is None
    assert period_returns(s, mode="diff")["1D"] == pytest.approx(1.0)


def test_returns_are_rounded():
    s = pd.Series([3.0, 4.0], index=pd.to_datetime(["2026-01-02", "2026-01-05"]))
    assert period_returns(s)["1D"] == 33.3333


# -- sparkline ---------------------------------------------------------------

def test_sparkline_downsamples_to_points_and_keeps_endpoints():
    s = bdays("2024-01-01", "2026-11-13")
    out = sparkline(s, months=12, points=52)
    assert len(out) == 52
    assert out[-1] == float(s.iloc[-1])
    window = s.loc[s.index[-1] - pd.DateOffset(months=12):]
    assert out[0] == float(window.iloc[0])
    assert out == sorted(out)  # monotone input stays monotone


def test_sparkline_short_series_untouched_and_rounded():
    s = pd.Series([1.1234567, 2.0, float("nan"), 3.0], index=pd.bdate_range("2026-11-09", periods=4))
    assert sparkline(s) == [1.123457, 2.0, 3.0]


def test_sparkline_empty():
    assert sparkline(pd.Series(dtype=float)) == []


# -- trailing_yield ----------------------------------------------------------

def test_trailing_yield_sums_last_12_months():
    close = pd.Series([100.0, 50.0], index=pd.to_datetime(["2026-01-02", "2026-11-13"]))
    divs = pd.Series(
        [9.0, 0.5, 0.5, 0.5, 0.5],
        index=pd.to_datetime(["2025-10-01", "2026-01-15", "2026-04-15", "2026-07-15", "2026-10-15"]),
    )
    assert trailing_yield(close, divs) == pytest.approx(4.0)


def test_trailing_yield_none_cases():
    close = pd.Series([100.0], index=pd.to_datetime(["2026-11-13"]))
    assert trailing_yield(close, pd.Series(dtype=float)) is None
    assert trailing_yield(pd.Series(dtype=float), pd.Series(dtype=float)) is None
