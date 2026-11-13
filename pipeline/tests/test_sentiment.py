import pandas as pd
import pytest

from pipeline.build import vix_term_structure
from pipeline.fetchers import cnn

PAYLOAD = {
    "fear_and_greed": {"score": 39.2, "rating": "fear", "timestamp": "2026-11-13T11:17:46+00:00",
                       "previous_close": 39.83, "previous_1_week": 24.35, "previous_1_month": 45.6,
                       "previous_1_year": 24.54},
    "fear_and_greed_historical": {"data": [
        {"x": 1794528000000.0, "y": 38.0, "rating": "fear"},
        {"x": 1794568666000.0, "y": 39.2, "rating": "fear"},  # same UTC day: last wins
    ]},
    "put_call_options": {"timestamp": 1794519213000.0, "score": 26.2, "rating": "fear",
                         "data": [{"x": 1794519213000.0, "y": 0.80012, "rating": "fear"}]},
    "junk_bond_demand": {"score": None},
}


def test_cnn_parse_headline_and_components():
    fg = cnn.parse(PAYLOAD)
    assert fg["score"] == 39.2 and fg["rating"] == "fear"
    assert fg["previous_1_week"] == 24.4
    assert len(fg["history"]) == 1 and fg["history"][0][1] == 39.2
    ids = [c["id"] for c in fg["components"]]
    assert ids == ["put_call_options"]  # missing/None components skipped
    assert fg["components"][0]["value"] == pytest.approx(0.8001)


def test_cnn_parse_missing_score_raises():
    with pytest.raises(ValueError):
        cnn.parse({"fear_and_greed": {}})


def test_vix_term_structure_uses_last_common_date():
    idx = pd.date_range("2025-11-01", periods=30, freq="B")
    close = pd.DataFrame({"^VIX": 18.0, "^VIX3M": 20.0, "^VIX9D": 17.0}, index=idx)
    close.iloc[-1, close.columns.get_loc("^VIX3M")] = float("nan")  # today not printed yet
    close.iloc[-2, close.columns.get_loc("^VIX")] = 22.0          # backwardation day
    out = vix_term_structure(close)
    assert out["asof"] == idx[-2].strftime("%Y-%m-%d")
    assert out["ratio"] == 1.1 and out["state"] == "backwardation"
    assert out["ratio_prev"] == 0.9
    assert out["vix9d"] == 17.0


def test_vix_term_structure_states():
    idx = pd.date_range("2026-01-01", periods=25, freq="B")
    calm = pd.DataFrame({"^VIX": 15.0, "^VIX3M": 18.0}, index=idx)
    assert vix_term_structure(calm)["state"] == "contango"
    flat = pd.DataFrame({"^VIX": 19.5, "^VIX3M": 20.0}, index=idx)
    assert vix_term_structure(flat)["state"] == "flat"
