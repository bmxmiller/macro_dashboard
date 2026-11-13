"""Tests for pure helpers in pipeline.build (import only, no network)."""
from __future__ import annotations

import pandas as pd

from pipeline.build import recession_periods


def usrec(values, start="2007-10-01") -> pd.Series:
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="MS"), dtype=float)


def test_no_recession():
    assert recession_periods(usrec([0, 0, 0])) == []
    assert recession_periods(pd.Series(dtype=float)) == []


def test_single_closed_recession_ends_at_first_non_recession_month():
    s = usrec([0, 0, 1, 1, 1, 0, 0])
    assert recession_periods(s) == [["2007-12-01", "2008-03-01"]]


def test_multiple_recessions():
    s = usrec([1, 0, 1, 1, 0, 0, 1, 0], start="2020-01-01")
    assert recession_periods(s) == [
        ["2020-01-01", "2020-02-01"],
        ["2020-03-01", "2020-05-01"],
        ["2020-07-01", "2020-08-01"],
    ]


def test_open_recession_runs_to_last_observation():
    s = usrec([0, 1, 1], start="2026-08-01")
    assert recession_periods(s) == [["2026-09-01", "2026-10-01"]]
