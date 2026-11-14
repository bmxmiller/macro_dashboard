"""Grounded-number validator."""
import pytest

from pipeline.ai import validate as V

DIGEST = {
    "markets": {"Sector Performance": {"1W": {"top": [{"name": "Energy", "tag": "XLE", "ret": 5.4, "unit": "%"}],
                                              "bottom": [{"name": "Technology", "tag": "XLK", "ret": -13.2, "unit": "%"}]}},
                "index_snapshot_1D": [{"name": "S&P 500", "tag": "SPY", "ret": -0.4, "unit": "%", "price": 754.37},
                                      {"name": "10Y Yield", "tag": "^TNX", "ret": -3, "unit": "bp"}]},
    "economy": {"claims": {"name": "Initial Jobless Claims", "value": 200, "prev": 191, "units": "k", "period": "07 NOV 2026"},
                "cpi_yoy": {"name": "CPI YoY", "value": 3.7, "prev": 3.4, "units": "%", "period": "SEP 2026", "z": 0.2}},
    "yield_curve": {"spreads": [{"label": "2s10s", "value_pct": 0.27, "value_bp": 27, "change_1m_bp": -15}]},
    "news": [{"id": "abc123def456", "source": "Reuters", "title": "Fed's Powell says 3 cuts unlikely"}],
}


def good_output(**over) -> dict:
    out = {
        "brief": {"headline": "Energy leads as tech slides 13.2%",
                  "bullets": ["CPI YoY rose to 3.7% from 3.4%.", "Claims at 200k.", "The S&P 500 fell 0.4% on the day."],
                  "what_moved": "Energy gained 5.4% over 1W; Technology fell -13.2%.",
                  "cycle_view": "The 2s10s spread is 27bp, 15bp tighter over 1M."},
        "news_clusters": [{"topic": "Fed", "summary": "Powell sees 3 cuts as unlikely.", "tags": ["rates"],
                           "item_ids": ["abc123def456"]}],
        "regime_explainer": {"rationale": "Growth rising.", "asset_tendencies": ["Equities tended to do well."],
                             "caveats": ["Data revisions."]},
    }
    out.update(over)
    return out


def test_grounded_output_passes():
    assert V.validate(good_output(), DIGEST) == []


@pytest.mark.parametrize("text", [
    "Energy rose 5.9% this week.",          # invented
    "CPI is 3.75%.",                        # extra precision not in the data
    "Claims jumped to 250k.",
    "The spread widened 40bp.",
    "Unemployment is 4.1%.",                # not in the digest at all
    "Brent hit $95 a barrel.",
])
def test_invented_numbers_rejected(text):
    out = good_output()
    out["brief"]["what_moved"] = text
    v = V.validate(out, DIGEST)
    assert len(v) == 1 and "brief.what_moved" in v[0]


@pytest.mark.parametrize("text", [
    "Energy rose about 5% this week.",      # coarser rounding of 5.4
    "Tech fell 13%.",                       # |−13.2| rounded, sign in prose
    "Claims were 200,000.",                 # 200 (k) written in full
    "The 2s10s curve sits at 0.27 percentage points.",
    "The 10Y yield moved 3 basis points.",
    "The S&P 500 is at 754.37, CPI 3.7%, over 6 months and 3 sectors in 2026.",
    "Over 1M and 3M, the 10Y and 2s10s were flat.",   # labels, not claims
    "CPI rose 3.7% (z-score 0.2).",
    "−13.2% and +5.4%",                     # unicode minus
])
def test_grounded_variants_accepted(text):
    out = good_output()
    out["brief"]["what_moved"] = text
    assert V.validate(out, DIGEST) == []


def test_extract_handles_signs_commas_units():
    got = [(n["value"], n["unit"], n["decimals"]) for n in V.extract("−1,234.5k, +27bp, -3.0%, $1.2bn, 4 percent")]
    assert got == [(-1234.5, "k", 1), (27.0, "bp", 0), (-3.0, "%", 1), (1.2, "bn", 1), (4.0, "%", 0)]


def test_small_integers_and_years_exempt_but_not_with_units():
    allowed = [3.7]
    assert V.is_grounded({"value": 7, "decimals": 0, "unit": ""}, allowed)
    assert V.is_grounded({"value": 1999, "decimals": 0, "unit": ""}, allowed)
    assert not V.is_grounded({"value": 7, "decimals": 0, "unit": "%"}, allowed)
    assert not V.is_grounded({"value": 45, "decimals": 0, "unit": ""}, allowed)


def test_ids_and_dates_in_digest_do_not_whitelist_numbers():
    allowed = V.allowed_numbers({"id": "123456", "date": "2026-11-13", "news": [{"id": "987654"}]})
    assert 123456 not in allowed and 987654 not in allowed and 13 not in allowed


def test_missing_fields_and_unknown_item_ids():
    out = good_output()
    del out["brief"]["cycle_view"]
    out["brief"]["bullets"] = ["one"]
    out["news_clusters"][0]["item_ids"] = ["nope"]
    del out["regime_explainer"]
    v = V.validate(out, DIGEST)
    joined = " | ".join(v)
    assert "brief.cycle_view" in joined and "brief.bullets" in joined
    assert "not in the digest: nope" in joined and "missing regime_explainer" in joined


def test_too_many_clusters():
    out = good_output(news_clusters=[good_output()["news_clusters"][0]] * 7)
    assert any("at most 6" in x for x in V.validate(out, DIGEST))


def test_non_object_output():
    assert V.validate(["x"], DIGEST) == ["output is not a JSON object"]
