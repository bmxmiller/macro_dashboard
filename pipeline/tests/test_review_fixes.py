"""Regression tests for issues found by the independent reviewer agent."""
from pathlib import Path

import pandas as pd
import pytest
import yaml

from pipeline.build import _minutes
from pipeline.fetchers.http import redact
from pipeline.transforms import econ

REGISTRY = Path(__file__).resolve().parents[1] / "registry"


# 1. Secrets must never reach logs or the public meta.json
def test_redact_strips_api_keys_from_urls():
    msg = "400 Client Error for url: https://api.stlouisfed.org/fred/x?series_id=CPI&api_key=SECRET123&file_type=json"
    out = redact(msg)
    assert "SECRET123" not in out
    assert "api_key=***" in out and "series_id=CPI" in out


# 2. YoY must span 12 months even when a month is missing (e.g. the Oct-2025 CPI gap)
def test_yoy_with_missing_month_is_not_13_months():
    idx = pd.date_range("2023-01-01", periods=36, freq="MS")
    s = pd.Series([100 * 1.0025 ** i for i in range(36)], index=idx)  # ~3.04%/yr, perfectly steady
    s = s.drop(idx[20])  # one unpublished month
    m = {"id": "x", "transform": "yoy", "series": "S", "frequency": "monthly"}
    out = econ.apply_transform(m, {"S": s})
    assert out.round(2).nunique() == 1, "every YoY reading should be the same ~3.04%"
    assert idx[20] not in out.index and idx[32] not in out.index  # gap months drop out


def test_mom_across_gap_is_not_doubled():
    idx = pd.date_range("2024-01-01", periods=6, freq="MS")
    s = pd.Series([100, 101, 102, 103, 104, 105], index=idx, dtype=float).drop(idx[3])
    out = econ.apply_transform({"id": "x", "transform": "mom_pct", "series": "S", "frequency": "monthly"}, {"S": s})
    assert idx[4] not in out.index  # m/m across the gap is undefined, not 2 months of change


# 3. Every registry file loads and has the keys the builders rely on
@pytest.mark.parametrize("path", sorted(REGISTRY.glob("*.yaml")), ids=lambda p: p.name)
def test_registry_files_parse(path):
    assert yaml.safe_load(path.read_text(encoding="utf-8"))


def test_metrics_registry_entries_complete():
    reg = yaml.safe_load((REGISTRY / "metrics.yaml").read_text(encoding="utf-8"))
    ids = set()
    for m in reg["metrics"]:
        assert m["id"] not in ids, f"duplicate id {m['id']}"
        ids.add(m["id"])
        assert m["transform"] in {"level", "yoy", "mom_pct", "diff", "ratio"}
        assert {"what", "why", "how_to_read"} <= set(m["about"]), m["id"]
        assert m["source_url"].startswith("http"), m["id"]
        assert ("numerator" in m and "denominator" in m) if m["transform"] == "ratio" else "series" in m


def test_universes_registry_entries_complete():
    uni = yaml.safe_load((REGISTRY / "universes.yaml").read_text(encoding="utf-8"))["panels"]
    for pid, p in uni.items():
        assert {"what", "why", "how_to_read"} <= set(p["about"]), pid
        for g in p["groups"]:
            for it in g["items"]:
                assert it["t"] and it["name"], (pid, it)


# 9. Calendar times sort chronologically, not alphabetically
def test_release_time_sorting():
    times = ["2:00 PM ET", "10:00 AM ET", "8:30 AM ET", None, "9:15 AM ET"]
    assert sorted(times, key=_minutes) == ["8:30 AM ET", "9:15 AM ET", "10:00 AM ET", "2:00 PM ET", None]
