from datetime import datetime

import pandas as pd
import pytest

from pipeline.fetchers import boe, ons


def test_parse_iadb_csv_multiple_codes_and_blanks():
    text = (
        "DATE,IUDBEDR,IUDMNZC\n"
        "02 Jan 2024,5.25,3.719\n"
        "03 Jan 2024,5.25,\n"
        "12 Nov 2026,4,5.21\n"
    )
    out = boe.parse_iadb_csv(text)
    assert set(out) == {"IUDBEDR", "IUDMNZC"}
    assert out["IUDBEDR"].index[-1] == pd.Timestamp("2026-11-12")
    assert out["IUDBEDR"].iloc[-1] == 4.0
    assert len(out["IUDMNZC"]) == 2  # blank dropped


def test_parse_iadb_csv_rejects_html_error_page():
    with pytest.raises(ValueError):
        boe.parse_iadb_csv("<!DOCTYPE html><html><body>Error</body></html>")


def test_parse_glc_sheet_picks_tenor_column():
    rows = [
        (None, "UK nominal spot curve", None, None),
        ("Maturity", None, None, None),
        ("years:", 0.5, 1, 2),
        ("#VALUE!", None, None, None),
        (datetime(2026, 11, 2), 4.20, 4.39, 4.62),
        (datetime(2026, 11, 3), 4.21, 4.40, ""),   # missing 2y value
        (datetime(2026, 11, 4), 4.22, 4.41, 4.64),
        (None, None, None, None),
    ]
    s = boe.parse_glc_sheet(rows, 2)
    assert list(s.index) == [pd.Timestamp("2026-11-02"), pd.Timestamp("2026-11-04")]
    assert s.iloc[-1] == pytest.approx(4.64)


def test_parse_glc_sheet_missing_tenor():
    with pytest.raises(ValueError):
        boe.parse_glc_sheet([("years:", 0.5, 1)], 2)


def test_ons_parse_monthly_and_quarterly():
    payload = {
        "months": [{"date": "2026 AUG", "value": "3.1"}, {"date": "2026 SEP", "value": "3.5"},
                   {"date": "2026 OCT", "value": ""}],
        "quarters": [{"date": "2026 Q2", "value": "0.5"}, {"date": "2026 Q3", "value": "0.7"}],
        "years": [],
    }
    m = ons.parse_timeseries(payload, "monthly")
    assert m.index[-1] == pd.Timestamp("2026-09-01") and m.iloc[-1] == 3.5
    assert len(m) == 2  # empty value skipped
    q = ons.parse_timeseries(payload, "quarterly")
    assert q.index[-1] == pd.Timestamp("2026-07-01")  # Q3 starts in July


def test_ons_parse_empty_raises():
    with pytest.raises(ValueError):
        ons.parse_timeseries({"months": []}, "monthly")


def test_ons_merge_vintages_newest_wins():
    qna = pd.Series({pd.Timestamp("2025-10-01"): 0.0, pd.Timestamp("2026-01-01"): 0.6,
                     pd.Timestamp("2026-04-01"): 0.5})
    pn2 = pd.Series({pd.Timestamp("2026-04-01"): 0.4, pd.Timestamp("2026-07-01"): 0.7})
    s = ons.merge_vintages([qna, pn2])
    assert list(s.values) == [0.0, 0.6, 0.4, 0.7]  # PN2 revises Q2 and adds Q3; QNA fills history


def test_uk_registry_is_complete():
    import yaml
    from pipeline.build import REGISTRY
    reg = yaml.safe_load((REGISTRY / "uk.yaml").read_text(encoding="utf-8"))
    groups = {g["id"] for g in reg["groups"]}
    for m in reg["metrics"]:
        assert m["group"] in groups
        assert m["source"] in {"ons", "boe", "boe_glc", "yahoo"}
        assert set(m["about"]) == {"what", "why", "how_to_read"}
        assert m["source_url"].startswith("https://")


def test_ons_lfs_rolling_window_dated_by_end_month():
    """ONS dates 3-month LFS averages by the MIDDLE month; we use the window's end."""
    import json
    from pathlib import Path
    payload = json.loads((Path(__file__).parent / "fixtures" / "ons_mgsx_lfs.json").read_text(encoding="utf-8"))
    s = ons.parse_timeseries(payload, "monthly")
    assert s.attrs["window_months"] == 3
    assert s.index[-1] == pd.Timestamp("2026-08-01") and s.iloc[-1] == 4.7   # JUN-AUG -> Aug
    assert pd.Timestamp("2026-02-01") in s.index                            # 2025 DEC-FEB ends in 2026
    assert pd.Timestamp("2026-01-01") in s.index                            # 2025 NOV-JAN ends in 2026
    assert ons.window_label(s.index[-1], 3) == "JUN–AUG 2026"
    assert ons.window_label(pd.Timestamp("2026-02-01"), 3) == "DEC 2025–FEB 2026"


def test_ons_single_month_labels_have_no_window():
    s = ons.parse_timeseries({"months": [{"date": "2026 AUG", "value": "3.7", "label": "2026 AUG"}]}, "monthly")
    assert s.index[-1] == pd.Timestamp("2026-08-01") and "window_months" not in s.attrs
