"""Deterministic regime rules on synthetic series (fixed 'today' so tests never age)."""
import pandas as pd
import pytest

from pipeline.ai import regime as R

TODAY = pd.Timestamp("2026-11-14")


def monthly(start: float, end: float, n: int = 12, last: str = "2026-09-01") -> list[list]:
    idx = pd.date_range(end=last, periods=n, freq="MS")
    step = (end - start) / (n - 1)
    return [[d.strftime("%Y-%m-%d"), start + i * step] for i, d in enumerate(idx)]


def weekly(level_old: float, level_new: float, n: int = 30, recent: int = 4) -> list[list]:
    idx = pd.date_range(end="2026-11-07", periods=n, freq="W-SAT")
    return [[d.strftime("%Y-%m-%d"), level_new if i >= n - recent else level_old] for i, d in enumerate(idx)]


def quarterly(values: list[float], last: str = "2026-07-01") -> list[list]:
    idx = pd.date_range(end=last, periods=len(values), freq="QS")
    return [[d.strftime("%Y-%m-%d"), v] for d, v in zip(idx, values)]


def metric(mid, hist, freq, value=None):
    return {"id": mid, "history": hist, "frequency": freq, "value": hist[-1][1] if value is None else value}


def economy(growth_up: bool, infl_up: bool, *, fed=4.5, pce_last=None, flat_infl=False) -> dict:
    g = 1 if growth_up else -1
    i = 0 if flat_infl else (1 if infl_up else -1)
    pce_hist = monthly(3.0, 3.0 + 0.6 * i)
    if pce_last is not None:
        pce_hist[-1][1] = pce_last
    return {"metrics": [
        metric("indpro_yoy", monthly(1.0, 1.0 + 1.5 * g), "monthly"),
        metric("claims", weekly(220, 220 - 20 * g), "weekly"),          # growth up ⇒ claims falling
        metric("gdp_qoq", quarterly([2.0] * 4 + [2.0 + 2 * g] * 2), "quarterly"),
        metric("core_cpi_yoy", monthly(3.0, 3.0 + 0.5 * i), "monthly"),
        metric("core_pce_yoy", pce_hist, "monthly"),
        metric("fed_funds", [["2026-11-13", fed]], "daily"),
    ]}


def regime(e, markets=None, today=TODAY):
    return R.compute_regime(e, markets, today=today)


@pytest.mark.parametrize("g,i,name", [
    (True, True, "Inflationary boom"),
    (True, False, "Goldilocks"),
    (False, True, "Stagflation"),
    (False, False, "Disinflationary slowdown"),
])
def test_four_quadrants(g, i, name):
    gi = regime(economy(g, i))["growth_inflation"]
    assert gi["quadrant"] == name and gi["label"] == name and not gi["boundary"]
    assert gi["allowed_quadrants"] == [name]
    assert gi["growth"]["state"] == ("accelerating" if g else "decelerating")
    assert gi["inflation"]["state"] == ("accelerating" if i else "decelerating")
    assert {c["id"] for c in gi["growth"]["components"]} == {"indpro", "claims", "gdp"}
    assert "direction of change, not the level" in gi["level_note"] and "2% target" in gi["level_note"]


def test_old_names_are_gone():
    assert "Reflation" not in R.QUADRANTS.values() and "Deflationary slowdown" not in R.QUADRANTS.values()


def test_component_math():
    m = {x["id"]: x for x in economy(True, True)["metrics"]}
    comps = {c["id"]: c for c in R.growth_signal(m, TODAY)["components"]}
    # linear ramp 1.0 → 2.5 over 11 monthly steps; a 6-month window spans 6 steps
    assert comps["indpro"]["value"] == pytest.approx(round(6 * 1.5 / 11, 2))
    assert comps["indpro"]["score"] == pytest.approx(round(6 * 1.5 / 11 / 2, 2))
    ma26 = (22 * 220 + 4 * 200) / 26  # 4w avg 200 vs 26w avg incl. the recent weeks
    assert comps["claims"]["value"] == pytest.approx(round((200 / ma26 - 1) * 100, 1))
    assert comps["claims"]["detail"] == {"avg_4w_k": 200.0, "avg_26w_k": round(ma26, 1)}
    # GDP: SAAR 2,2,2,2,4,4 → YoY now from (2,2,4,4), 2q ago from (2,2,2,2)
    f = lambda qs: ((pd.Series(qs) / 100 + 1) ** 0.25).prod() * 100 - 100  # noqa: E731
    assert comps["gdp"]["value"] == pytest.approx(round(f([2, 2, 4, 4]) - f([2, 2, 2, 2]), 2))
    assert comps["gdp"]["detail"]["yoy_now_pct"] == pytest.approx(round(f([2, 2, 4, 4]), 2))


def test_claims_sustained_10pct_jump_scores_about_minus_083():
    s = pd.Series([200.0] * 22 + [220.0] * 4, index=pd.date_range(end="2026-11-07", periods=26, freq="W-SAT"))
    ratio = R.claims_trend(s)[2]
    assert -ratio / 0.10 == pytest.approx(-0.83, abs=0.01)


def test_scores_are_clipped():
    e = economy(True, True)
    e["metrics"][0]["history"] = monthly(0, 40)  # absurd jump in INDPRO YoY
    gi = regime(e)["growth_inflation"]
    assert max(c["score"] for c in gi["growth"]["components"]) == 1.0


def test_flat_axis_is_a_boundary():
    gi = regime(economy(True, False, flat_infl=True))["growth_inflation"]
    assert gi["inflation"]["score"] == 0 and gi["inflation"]["state"] == "flat"
    assert gi["quadrant"] == "Goldilocks"  # 0 counts as down
    assert gi["boundary"] and gi["label"] == "Goldilocks / Inflationary boom boundary"
    assert set(gi["allowed_quadrants"]) == {"Goldilocks", "Inflationary boom"}


def test_both_axes_flat_is_centre():
    flat = {"metrics": [metric("core_cpi_yoy", monthly(3, 3), "monthly"), metric("core_pce_yoy", monthly(3, 3), "monthly"),
                        metric("indpro_yoy", monthly(1, 1), "monthly")]}
    gi = regime(flat)["growth_inflation"]
    assert gi["boundary"] and gi["label"].startswith("Near the centre") and len(gi["allowed_quadrants"]) == 4


def test_missing_data_gives_no_quadrant():
    assert regime({"metrics": [metric("gdp_qoq", quarterly([2] * 6), "quarterly")]})["growth_inflation"]["quadrant"] is None
    assert regime(None)["growth_inflation"]["quadrant"] is None


def test_change_over_needs_an_observation_near_the_target():
    s = pd.Series({pd.Timestamp(d): v for d, v in monthly(1, 2)})
    assert R.change_over(s) is not None
    gappy = s.drop(pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01"]))
    assert R.change_over(gappy) is None  # nearest earlier obs is Dec 2025, > 35 days before 1 Mar


def test_gdp_needs_six_gap_free_quarters():
    s = pd.Series({pd.Timestamp(d): v for d, v in quarterly([2] * 6)})
    assert R.gdp_momentum(s) is not None
    assert R.gdp_momentum(s.drop(s.index[2])) is None
    assert R.gdp_momentum(s.iloc[-5:]) is None


def test_stale_inputs_are_dropped_and_listed():
    r = regime(economy(True, True), today=pd.Timestamp("2027-06-30"))
    assert r["growth_inflation"]["quadrant"] is None
    assert {"indpro_yoy", "claims", "gdp_qoq", "core_cpi_yoy", "core_pce_yoy", "fed_funds"} <= set(r["stale_inputs"])
    assert r["growth_policy"]["stance"] is None


@pytest.mark.parametrize("fed,pce,stance,borderline", [
    (4.5, 3.0, "restrictive", False),      # mid 4.375 → real 1.375
    (4.0, 3.2, "neutral", False),          # mid 3.875 → real 0.675
    (4.0, 2.875, "neutral", True),         # real exactly 1.0: band edge is neutral, borderline
    (3.625, 3.0, "neutral", True),         # real exactly 0.5
    (4.0, 2.871, "restrictive", True),     # real 1.004: classified unrounded although it shows 1.0
    (3.0, 3.0, "accommodative", False),    # real −0.125
])
def test_policy_stance_uses_midpoint(fed, pce, stance, borderline):
    gp = regime(economy(True, False, fed=fed, pce_last=pce))["growth_policy"]
    assert gp["stance"] == stance and gp["borderline"] == borderline
    assert gp["fed_funds_mid_pct"] == pytest.approx(fed - 0.125)
    assert gp["real_rate_pct"] == pytest.approx(round(fed - 0.125 - pce, 2))
    assert gp["label"].startswith(stance.capitalize()) and "rising" in gp["label"]
    assert "r*" in gp["note"]


def test_policy_missing_inputs():
    gp = R.growth_policy({}, None)
    assert gp["stance"] is None and gp["label"] is None


def markets(hyg, iei, lqd, ief) -> dict:
    rows = [{"ticker": t, "returns": {"3M": v}} for t, v in (("HYG", hyg), ("IEI", iei), ("LQD", lqd), ("IEF", ief))]
    return {"panels": {"fixed_income": {"groups": [{"rows": rows}]}}}


@pytest.mark.parametrize("args,leader,borderline", [
    ((3.0, -1.0, 1.0, 0.0), "credit", False),      # mean +2.5
    ((-2.0, 4.0, 0.0, 1.5), "duration", False),    # mean −3.75
    ((1.0, 0.8, 0.5, 0.6), "balanced", False),     # mean +0.05
    ((1.0, 0.0, 0.0, 0.0), "balanced", True),      # mean exactly +0.5 → not above the deadband
    ((1.4, 0.0, 0.0, 0.0), "credit", True),        # +0.7, within 0.25 of the threshold
])
def test_credit_duration(args, leader, borderline):
    cd = R.credit_duration(markets(*args))
    assert cd["leader"] == leader and cd["borderline"] == borderline and len(cd["pairs"]) == 2
    assert [(p["long"], p["short"]) for p in cd["pairs"]] == [("HYG", "IEI"), ("LQD", "IEF")]
    assert cd["pairs"][0]["spread_pp"] == pytest.approx(round(args[0] - args[1], 1))


def test_hy_oas_cross_check():
    days = pd.bdate_range(end="2026-11-12", periods=80)
    oas = {"hy_oas": {"history": [[d.strftime("%Y-%m-%d"), 4.0 - 0.01 * i] for i, d in enumerate(days)]}}
    cd = R.credit_duration(markets(3.0, -1.0, 1.0, 0.0), oas)
    assert cd["hy_oas_3m_chg_bp"] < 0 and cd["hy_oas_confirms"] is True


def test_credit_duration_missing_rows():
    cd = R.credit_duration({"panels": {}})
    assert cd["leader"] is None and cd["pairs"] == []
