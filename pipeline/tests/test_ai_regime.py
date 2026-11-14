"""Deterministic regime rules on synthetic series."""
import pandas as pd
import pytest

from pipeline.ai import regime as R


def monthly(start: float, end: float, n: int = 12) -> list[list]:
    idx = pd.date_range("2025-10-01", periods=n, freq="MS")
    step = (end - start) / (n - 1)
    return [[d.strftime("%Y-%m-%d"), start + i * step] for i, d in enumerate(idx)]


def weekly(level_old: float, level_new: float, n: int = 30, recent: int = 4) -> list[list]:
    idx = pd.date_range("2026-04-04", periods=n, freq="W-SAT")
    return [[d.strftime("%Y-%m-%d"), level_new if i >= n - recent else level_old] for i, d in enumerate(idx)]


def quarterly(last: float) -> list[list]:
    return [["2026-01-01", 2.0], ["2026-04-01", 2.0], ["2026-07-01", last]]


def economy(growth_up: bool, infl_up: bool, *, fed=4.5, pce_last=None) -> dict:
    g = 1 if growth_up else -1
    i = 1 if infl_up else -1
    pce_hist = monthly(3.0, 3.0 + 0.6 * i)
    if pce_last is not None:
        pce_hist[-1][1] = pce_last
    metrics = {
        "indpro_yoy": monthly(1.0, 1.0 + 1.5 * g),
        "claims": weekly(220, 220 - 20 * g),        # growth up ⇒ claims falling
        "gdp_qoq": quarterly(1.8 + 1.5 * g),
        "core_cpi_yoy": monthly(3.0, 3.0 + 0.5 * i),
        "core_pce_yoy": pce_hist,
        "fed_funds": [["2026-11-13", fed]],
    }
    out = [{"id": k, "history": h, "value": h[-1][1]} for k, h in metrics.items()]
    return {"metrics": out}


@pytest.mark.parametrize("g,i,name", [
    (True, True, "Reflation"),
    (True, False, "Goldilocks"),
    (False, True, "Stagflation"),
    (False, False, "Deflationary slowdown"),
])
def test_four_quadrants(g, i, name):
    gi = R.compute_regime(economy(g, i), None)["growth_inflation"]
    assert gi["quadrant"] == name
    assert (gi["growth"]["score"] > 0) == g and (gi["inflation"]["score"] > 0) == i
    assert -1 <= gi["growth"]["score"] <= 1 and -1 <= gi["inflation"]["score"] <= 1
    assert {c["id"] for c in gi["growth"]["components"]} == {"indpro", "claims", "gdp"}
    assert not gi["borderline"]


def test_component_math():
    m = {x["id"]: x for x in economy(True, True)["metrics"]}
    comps = {c["id"]: c for c in R.growth_signal(m)["components"]}
    # linear ramp 1.0 → 2.5 over 11 monthly steps; a 6-month window spans 6 steps
    assert comps["indpro"]["value"] == pytest.approx(round(6 * 1.5 / 11, 2))
    assert comps["indpro"]["score"] == pytest.approx(round(6 * 1.5 / 11 / 2, 2))
    # claims: 4w avg 200 vs 26w avg (22*220 + 4*200)/26
    ma26 = (22 * 220 + 4 * 200) / 26
    assert comps["claims"]["value"] == pytest.approx(round((200 / ma26 - 1) * 100, 1))
    assert comps["claims"]["score"] > 0  # falling claims = growth up
    assert comps["gdp"]["value"] == pytest.approx(1.5) and comps["gdp"]["score"] == pytest.approx(0.75)


def test_scores_are_clipped():
    e = economy(True, True)
    for m in e["metrics"]:
        if m["id"] == "indpro_yoy":
            m["history"] = monthly(0, 40)  # absurd jump
    gi = R.compute_regime(e, None)["growth_inflation"]
    assert max(c["score"] for c in gi["growth"]["components"]) == 1.0


def test_zero_score_counts_as_down_and_borderline():
    flat = {"metrics": [
        {"id": "core_cpi_yoy", "history": monthly(3.0, 3.0)},
        {"id": "core_pce_yoy", "history": monthly(3.0, 3.0)},
        {"id": "gdp_qoq", "history": quarterly(2.5)},
    ]}
    gi = R.compute_regime(flat, None)["growth_inflation"]
    assert gi["inflation"]["score"] == 0 and gi["inflation"]["direction"] == "down"
    assert gi["quadrant"] == "Goldilocks" and gi["borderline"]


def test_missing_data_gives_no_quadrant():
    gi = R.compute_regime({"metrics": [{"id": "gdp_qoq", "history": quarterly(3.0)}]}, None)["growth_inflation"]
    assert gi["quadrant"] is None and gi["inflation"]["score"] is None
    assert R.compute_regime(None, None)["growth_inflation"]["quadrant"] is None


def test_short_history_skips_component():
    e = {"metrics": [{"id": "indpro_yoy", "history": monthly(1, 2, n=3)},   # < 6 months
                     {"id": "claims", "history": weekly(200, 210, n=10)}]}   # < 26 weeks
    assert R.growth_signal({m["id"]: m for m in e["metrics"]})["components"] == []


@pytest.mark.parametrize("fed,pce,stance", [
    (4.5, 3.0, "restrictive"),     # real 1.5
    (4.0, 3.2, "neutral"),         # real 0.8
    (4.0, 3.0, "neutral"),         # real 1.0: band edge is neutral
    (3.5, 3.0, "neutral"),         # real 0.5: band edge is neutral
    (3.0, 3.0, "accommodative"),   # real 0.0
])
def test_policy_stance(fed, pce, stance):
    gp = R.compute_regime(economy(True, False, fed=fed, pce_last=pce), None)["growth_policy"]
    assert gp["stance"] == stance and gp["real_rate"] == pytest.approx(fed - pce)
    assert gp["label"].startswith(stance.capitalize()) and "rising" in gp["label"]


def test_policy_missing_inputs():
    gp = R.growth_policy({}, None)
    assert gp["stance"] is None and gp["label"] is None


def markets(hyg, tlt, lqd, ief) -> dict:
    rows = [{"ticker": t, "returns": {"3M": v}} for t, v in (("HYG", hyg), ("TLT", tlt), ("LQD", lqd), ("IEF", ief))]
    return {"panels": {"fixed_income": {"groups": [{"rows": rows}]}}}


@pytest.mark.parametrize("args,leader", [
    ((3.0, -1.0, 1.0, 0.0), "credit"),
    ((-2.0, 4.0, 0.0, 1.5), "duration"),
    ((1.0, 0.8, 0.5, 0.6), "balanced"),
    ((1.0, 0.0, 0.0, 0.0), "balanced"),   # mean spread exactly 0.5 → not above the deadband
])
def test_credit_duration(args, leader):
    cd = R.credit_duration(markets(*args))
    assert cd["leader"] == leader and len(cd["pairs"]) == 2
    assert cd["pairs"][0]["spread"] == pytest.approx(round(args[0] - args[1], 1))


def test_credit_duration_missing_rows():
    cd = R.credit_duration({"panels": {}})
    assert cd["leader"] is None and cd["pairs"] == []
