"""Tests for pipeline.transforms.econ (pure, offline)."""
from __future__ import annotations

import pandas as pd
import pytest

from pipeline.transforms import econ


def monthly(values, start="2020-01-01") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


# -- to_regular --------------------------------------------------------------

def test_to_regular_monthly_takes_last_obs_per_month():
    s = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2026-01-05", "2026-01-28", "2026-02-10"]))
    out = econ.to_regular(s, "monthly")
    assert list(out.index) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-02-01")]
    assert list(out.values) == [2.0, 3.0]


def test_to_regular_quarterly():
    s = pd.Series([1.0, 2.0, 3.0], index=pd.to_datetime(["2026-01-01", "2026-03-31", "2026-04-01"]))
    out = econ.to_regular(s, "quarterly")
    assert list(out.index) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-04-01")]
    assert list(out.values) == [2.0, 3.0]


def test_to_regular_other_frequency_passthrough():
    s = pd.Series([1.0, 2.0], index=pd.to_datetime(["2026-01-05", "2026-01-06"]))
    assert econ.to_regular(s, "daily") is s


# -- apply_transform ---------------------------------------------------------

def test_level():
    s = monthly([1.0, 2.0, 3.0])
    out = econ.apply_transform({"id": "x", "transform": "level", "series": "A"}, {"A": s})
    assert list(out.values) == [1.0, 2.0, 3.0]


def test_yoy_monthly():
    s = monthly([100.0] * 12 + [103.0, 110.0])
    out = econ.apply_transform({"id": "cpi", "transform": "yoy", "series": "A", "frequency": "monthly"}, {"A": s})
    assert len(out) == 2
    assert out.iloc[0] == pytest.approx(3.0)
    assert out.iloc[1] == pytest.approx(10.0)
    assert out.index[0] == pd.Timestamp("2021-01-01")


def test_yoy_quarterly():
    s = pd.Series([100.0, 101.0, 102.0, 103.0, 105.0],
                  index=pd.date_range("2024-01-01", periods=5, freq="QS"))
    out = econ.apply_transform({"id": "g", "transform": "yoy", "series": "A", "frequency": "quarterly"}, {"A": s})
    assert len(out) == 1
    assert out.iloc[0] == pytest.approx(5.0)


def test_yoy_defaults_to_monthly():
    s = monthly([100.0] * 12 + [104.0])
    out = econ.apply_transform({"id": "x", "transform": "yoy", "series": "A"}, {"A": s})
    assert list(out.values) == pytest.approx([4.0])


def test_yoy_rejects_daily():
    with pytest.raises(ValueError):
        econ.apply_transform({"id": "x", "transform": "yoy", "series": "A", "frequency": "daily"},
                             {"A": monthly([1.0, 2.0])})


def test_mom_pct():
    out = econ.apply_transform({"id": "x", "transform": "mom_pct", "series": "A"},
                               {"A": monthly([100.0, 102.0, 99.96])})
    assert list(out.round(6).values) == [2.0, -2.0]


def test_diff():
    out = econ.apply_transform({"id": "x", "transform": "diff", "series": "A"},
                               {"A": monthly([100.0, 250.0, 200.0])})
    assert list(out.values) == [150.0, -50.0]


def test_ratio_with_multiplier_aligns_and_drops_missing():
    num = monthly([10.0, 20.0, 30.0])
    den = monthly([100.0, 200.0])
    out = econ.apply_transform(
        {"id": "r", "transform": "ratio", "numerator": "N", "denominator": "D", "multiplier": 100},
        {"N": num, "D": den},
    )
    assert list(out.values) == [10.0, 10.0]


def test_scale():
    out = econ.apply_transform({"id": "x", "transform": "level", "series": "A", "scale": 0.001},
                               {"A": monthly([1000.0, 2000.0])})
    assert list(out.values) == pytest.approx([1.0, 2.0])


def test_unknown_transform():
    with pytest.raises(ValueError):
        econ.apply_transform({"id": "x", "transform": "nope", "series": "A"}, {"A": monthly([1.0])})


# -- zscore / percentile -----------------------------------------------------

def test_zscore():
    s = monthly([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0])
    expected = (9.0 - s.mean()) / s.std()
    assert econ.zscore(s) == round(expected, 2)


def test_zscore_none_cases():
    assert econ.zscore(monthly([1.0] * 7)) is None  # too short
    assert econ.zscore(monthly([5.0] * 20)) is None  # zero std


def test_zscore_uses_trailing_window():
    s = monthly([1000.0] * 12 + [1.0, 2.0] * 30, start="2000-01-01")
    win = s.loc[s.index[-1] - pd.DateOffset(years=2):]
    assert econ.zscore(s, years=2) == round((s.iloc[-1] - win.mean()) / win.std(), 2)


def test_percentile():
    assert econ.percentile(monthly([float(v) for v in range(1, 11)])) == 100.0
    assert econ.percentile(monthly([float(v) for v in range(10, 0, -1)])) == 10.0
    assert econ.percentile(monthly([1.0] * 5)) is None


# -- period_label ------------------------------------------------------------

def test_period_label():
    assert econ.period_label(pd.Timestamp("2026-05-01"), "monthly") == "MAY 2026"
    assert econ.period_label(pd.Timestamp("2026-07-01"), "quarterly") == "Q3 2026"
    assert econ.period_label(pd.Timestamp("2026-11-07"), "weekly") == "07 NOV 2026"


# -- history -----------------------------------------------------------------

def test_history_format_and_window():
    s = monthly([1.23456, 2.0, 3.0], start="2026-01-01")
    assert econ.history(s) == [["2026-01-01", 1.2346], ["2026-02-01", 2.0], ["2026-03-01", 3.0]]
    long = monthly([1.0] * 400, start="1990-01-01")
    h = econ.history(long, years=10)
    assert len(h) == 121
    assert h[-1][0] == long.index[-1].strftime("%Y-%m-%d")


def test_history_downsamples_daily_to_weekly():
    s = pd.Series(range(1000), index=pd.bdate_range("2023-01-02", periods=1000), dtype=float)
    h = econ.history(s, max_points=600)
    assert 100 < len(h) < 600
    dates = pd.to_datetime([d for d, _ in h])
    assert all(d.day_of_week == 6 for d in dates)  # week-ending (Sunday) labels
    assert h[-1][1] == 999.0  # latest value preserved
