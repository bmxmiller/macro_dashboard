"""Validator building blocks: extraction, facts, structure. (Adversarial cases: test_ai_validate_adversarial.py.)"""
import pytest

from pipeline.ai import validate as V
from pipeline.tests.test_ai_validate_adversarial import DIGEST, NEWS_ID, out_with


def parsed(text, names=()):
    return [(c.value, c.unit, c.decimals) for c in V.extract(text, names)]


@pytest.mark.parametrize("text,expected", [
    ("−1,234.5k, +27bp, -3.0%, $1.2bn, 4 percent", [(-1234.5, "k", 1), (27.0, "bp", 0), (-3.0, "%", 1), (1.2, "bn", 1), (4.0, "%", 0)]),
    ("250K and 9 % and 10 bp", [(250.0, "k", 0), (9.0, "%", 0), (10.0, "bp", 0)]),
    ("down 1.5pc", [(1.5, "%", 1)]),                       # never truncated to 1
    ("4,512.5K", [(4512.5, "k", 1)]),
    ("27 basis points and 1.5 percentage points", [(27.0, "bp", 0), (1.5, "pp", 1)]),
    ("1.5 million and 2 billion", [(1.5, "m", 1), (2.0, "bn", 0)]),
])
def test_extract_units_signs_commas(text, expected):
    assert parsed(text) == expected


@pytest.mark.parametrize("text", [
    "the 10Y and 2s10s over 1M, 3M and 6M", "the 3m10y spread", "36th percentile", "a 30-year bond",
    "Treasury 7-10Y", "on 2026-11-13", "as of Nov 13", "13 November", "in 2026", "at 8:30",
])
def test_labels_dates_and_years_are_not_claims(text):
    assert parsed(text) == []


def test_names_are_masked():
    assert parsed("The S&P 500 and Russell 2000 and Nasdaq 100 moved") == []
    assert parsed("Energy XLE fund", names=["Treasury 20+"]) == []


def test_spelled_numbers_detected():
    assert V.spelled_numbers("payrolls rose by two hundred thousand")
    assert V.spelled_numbers("up five percent")
    assert not V.spelled_numbers("three sectors rose")


def test_nearest_alias_in_clause():
    t = "CPI rose to 3.7%, while core CPI was 2.6%"
    assert V.nearest_alias(t, t.index("3.7")) == "cpi"
    assert V.nearest_alias(t, t.index("2.6")) == "core_cpi"
    t2 = "The Dow is above 40,000"
    assert V.nearest_alias(t2, t2.index("40")) is None  # "above" starts a new clause


def test_facts_skip_names_periods_and_ids():
    facts, headline, _ = V.digest_facts(DIGEST)
    values = {abs(f.value) for f in facts}
    assert 500 not in values and 2026 not in values and 13 not in values  # names / periods / dates
    assert {h.value for h in headline} == {0.3}


def test_prev_needs_context():
    assert V.validate(out_with("Claims rose to 200k from 191k."), DIGEST) == []
    assert V.validate(out_with("Claims are 191k."), DIGEST)


def test_missing_fields_and_unknown_item_ids():
    out = out_with("Stocks were mixed.")
    del out["brief"]["cycle_view"]
    out["brief"]["bullets"] = ["one"]
    out["news_clusters"][0]["item_ids"] = ["nope"]
    del out["regime_explainer"]
    joined = " | ".join(V.validate(out, DIGEST))
    assert "brief.cycle_view" in joined and "brief.bullets" in joined
    assert "not in the digest: nope" in joined and "missing regime_explainer" in joined


def test_too_many_clusters():
    out = out_with("Stocks were mixed.")
    out["news_clusters"] = [out["news_clusters"][0]] * 7
    assert any("at most 6" in x for x in V.validate(out, DIGEST))


def test_non_object_output():
    assert V.validate(["x"], DIGEST) == ["output is not a JSON object"]


def test_violation_messages_explain_the_fix():
    v = " ".join(V.validate(out_with("Core CPI rose to 3.7%. Energy rose 5%. VIX at 19.3%."), DIGEST))
    assert "core cpi" in v and "coarsely" in v and "unit" in v
    assert NEWS_ID  # fixture sanity
