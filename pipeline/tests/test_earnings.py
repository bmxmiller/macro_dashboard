from datetime import date

import pandas as pd
import yaml

from pipeline.fetchers import earnings


def _df(rows):
    idx = pd.to_datetime([t for t, *_ in rows], utc=True).tz_convert("America/New_York")
    return pd.DataFrame({"EPS Estimate": [r[1] for r in rows], "Reported EPS": [r[2] for r in rows]}, index=idx)


def test_time_of_day():
    ny = "America/New_York"
    assert earnings.time_of_day(pd.Timestamp("2026-11-17 06:00", tz=ny)) == "BMO"
    assert earnings.time_of_day(pd.Timestamp("2026-11-17 16:00", tz=ny)) == "AMC"
    assert earnings.time_of_day(pd.Timestamp("2026-11-17 12:00", tz=ny)) == "DMH"
    assert earnings.time_of_day(pd.Timestamp("2026-11-17 00:00", tz=ny)) is None
    # UTC input is converted to New York time (21:00 UTC = 16:00 EST)
    assert earnings.time_of_day(pd.Timestamp("2026-11-17 21:00", tz="UTC")) == "AMC"


def test_parse_earnings_dates_next_report_and_prior_year():
    df = _df([
        ("2026-11-17 16:00-05:00", 2.47, float("nan")),
        ("2026-08-26 16:00-04:00", 2.09, 2.22),
        ("2026-05-20 16:00-04:00", 1.77, 1.87),
        ("2025-11-19 16:00-05:00", 1.26, 1.30),
        ("2025-08-27 16:00-04:00", 1.01, 1.05),
    ])
    out = earnings.parse_earnings_dates(df, date(2026, 11, 13), 14)
    assert out == {"date": "2026-11-17", "time": "AMC", "eps_estimate": 2.47,
                   "eps_prior_year": 1.30, "prior_year_date": "2025-11-19"}


def test_parse_earnings_dates_outside_window():
    df = _df([("2027-01-28 16:00-05:00", 2.91, float("nan")), ("2026-11-02 16:00-05:00", 1.98, 2.10)])
    assert earnings.parse_earnings_dates(df, date(2026, 11, 13), 14) is None
    assert earnings.parse_earnings_dates(pd.DataFrame(), date(2026, 11, 13), 14) is None


def test_parse_calendar_fallback():
    cal = {"Earnings Date": [date(2026, 11, 19)], "Earnings Average": 0.63488}
    out = earnings.parse_calendar(cal, date(2026, 11, 13), 14)
    assert out["date"] == "2026-11-19" and out["eps_estimate"] == 0.6349 and out["time"] is None
    assert earnings.parse_calendar({"Earnings Date": [date(2027, 1, 1)]}, date(2026, 11, 13), 14) is None
    assert earnings.parse_calendar({}, date(2026, 11, 13), 14) is None


def test_registry_has_unique_tickers():
    from pipeline.build import REGISTRY
    reg = yaml.safe_load((REGISTRY / "earnings.yaml").read_text(encoding="utf-8"))
    tickers = [c["t"] for c in reg["companies"]]
    assert len(tickers) == len(set(tickers)) >= 55
