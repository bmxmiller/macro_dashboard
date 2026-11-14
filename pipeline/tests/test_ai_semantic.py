"""Semantic guards: advice words, regime names, contradictions; code-authored tendencies."""
import copy

import pytest
import yaml

from pipeline.ai import llm
from pipeline.ai import validate as V
from pipeline.tests.test_ai_validate_adversarial import DIGEST, out_with


@pytest.mark.parametrize("text", [
    "Investors should buy equities.",
    "Now may be a time to sell bonds.",
    "We recommend an overweight in energy.",
    "Stay underweight duration.",
    "Equities always do well here.",
    "This works every time.",
    "Gains are guaranteed.",
    "Gold will rise further.",
    "Stocks will likely outperform bonds.",
    "The economy is in Stagflation.",                 # computed: Goldilocks
    "A Reflation regime is under way.",               # legacy / Clock name
    "Growth is decelerating.",                        # computed: accelerating
    "Inflation is re-accelerating.",                  # computed: decelerating
    "Policy is restrictive.",                         # computed: neutral
    "Monetary policy remains tight.",
    "Credit is leading duration.",                    # computed: balanced
])
def test_semantic_violations(text):
    assert V.validate(out_with(text, "cycle_view"), DIGEST), text


@pytest.mark.parametrize("text", [
    "The economy sits in Goldilocks: growth is accelerating while inflation is decelerating.",
    "Policy is neutral and credit and duration are balanced.",
    "The sell-off in tech deepened.",
    "Equities have historically tended to do well in this phase, but past patterns are not forecasts.",
])
def test_semantic_ok(text):
    assert V.validate(out_with(text, "cycle_view"), DIGEST) == []


@pytest.mark.parametrize("text", [
    # exact sentence seen in the first live brief
    "The US 10Y Yield rose with a 5 bp increase to a level_pct of 5.15.",
    "The S&P 500 gained per ret_1w_pct.",
    "The 10-year moved by chg_1d_bp.",
])
def test_internal_field_names_rejected(text):
    v = V.validate(out_with(text), DIGEST)
    assert any("internal field name" in x for x in v), (text, v)


def test_plain_english_is_not_flagged_as_field_name():
    for text in ["The 10Y yield rose 5 bp to 5.15%.", "Year-over-year growth: S&P 500 fell 0.4%.",
                 "A risk-on, short-term move in non-farm payrolls."]:
        assert not V.check_field_names("brief.what_moved", text), text


def test_boundary_allows_both_neighbouring_names():
    d = copy.deepcopy(DIGEST)
    d["regime"]["growth_inflation"].update(label="Goldilocks / Inflationary boom boundary", boundary=True,
                                           allowed_quadrants=["Goldilocks", "Inflationary boom"])
    assert V.validate(out_with("On the Goldilocks / Inflationary boom boundary.", "cycle_view"), d) == []
    assert V.validate(out_with("Close to Stagflation.", "cycle_view"), d)


def test_tendencies_are_code_authored_hedged_and_cited():
    cfg = llm.load_config()
    t = cfg["regime_tendencies"]
    assert "Greetham & Hartnett (2004)" in t["basis"] and "not forecasts" in t["basis"]
    assert set(t["quadrants"]) == {"Goldilocks", "Inflationary boom", "Stagflation", "Disinflationary slowdown"}
    for items in t["quadrants"].values():
        for it in items:
            assert "historically" in it["text"] or "sometimes" in it["text"]
            assert not V.ADVICE.search(it["text"]), it["text"]
    # the LLM schema has no tendencies field: it cannot write them
    from pipeline.ai.insights import RESPONSE_SCHEMA
    assert "asset_tendencies" not in yaml.safe_dump(RESPONSE_SCHEMA)


def _with_components(**scores):
    d = copy.deepcopy(DIGEST)
    gi = d["regime"]["growth_inflation"]
    for metric, s in scores.items():
        side = "inflation" if metric.startswith("core") else "growth"
        gi[side]["components"].append({"label": metric, "metric": metric, "score": s})
    return d


def test_component_wording_must_match_its_score():
    # The live gemini-3.5-flash-lite answer (2026-11-14) passed every numeric check but said this
    # while the GDP momentum component was −0.57 (decelerating).
    d = _with_components(gdp=-0.57, indpro=0.78, core_cpi=-0.04)
    bad = "Real GDP YoY and industrial production point to firmer activity."
    v = V.validate(out_with(bad, "cycle_view"), d)
    assert len(v) == 1 and "GDP" in v[0] and "-0.57" in v[0]
    assert V.validate(out_with("Industrial production points to firmer activity, while GDP momentum is softer.",
                               "cycle_view"), d) == []
    assert V.validate(out_with("Core CPI is firming.", "cycle_view"), d)  # flat (−0.04)
