"""Adversarial grounding cases from the PR #3 review. Every BAD string must be rejected and every
GOOD string accepted. The digest is hand-built (stable), in the same shape context.py produces."""
import copy

import pytest

from pipeline.ai import validate as V

NEWS_ID = "abc123def456"
DIGEST = {
    "markets": {
        "index_snapshot": [
            {"name": "S&P 500", "tag": "SPY", "ret_1d_pct": -0.4, "asof": "2026-11-13", "source": "Yahoo Finance"},
            {"name": "Nasdaq 100", "tag": "QQQ", "ret_1d_pct": -1.2, "asof": "2026-11-13", "source": "Yahoo Finance"},
            {"name": "Dow Jones", "tag": "DIA", "ret_1d_pct": 0.1, "asof": "2026-11-13", "source": "Yahoo Finance"},
            {"name": "Russell 2000", "tag": "IWM", "ret_1d_pct": -0.3, "asof": "2026-11-13", "source": "Yahoo Finance"},
            {"name": "VIX", "tag": "INDEX", "ret_1d_pct": 3.2, "level": 19.3, "asof": "2026-11-13", "source": "Yahoo Finance"},
            {"name": "US 10Y Yield", "tag": "%", "chg_1d_bp": 5, "level_pct": 5.15, "asof": "2026-11-13", "source": "Yahoo Finance"},
            {"name": "Gold", "tag": "FUT", "ret_1d_pct": 0.0, "level": 3886.3, "asof": "2026-11-13", "source": "Yahoo Finance"},
        ],
        "Sector Performance": {
            "1W": {"top": [{"name": "Energy", "tag": "XLE", "ret_pct": 5.4}], "bottom": [{"name": "Materials", "tag": "XLB", "ret_pct": 0.5}]},
            "1M": {"top": [{"name": "Financials", "tag": "XLF", "ret_pct": 7.0}],
                   "bottom": [{"name": "Technology", "tag": "XLK", "ret_pct": -13.2}]},
        },
    },
    "economy": {
        "cpi_yoy": {"name": "CPI YoY", "value": 3.7, "prev": 3.4, "units": "%", "period": "SEP 2026", "z": 0.2, "source": "FRED"},
        "core_cpi_yoy": {"name": "Core CPI YoY", "value": 2.6, "prev": 2.4, "units": "%", "period": "SEP 2026", "z": -0.4, "source": "FRED"},
        "core_pce_yoy": {"name": "Core PCE YoY", "value": 3.1, "prev": 3.0, "units": "%", "period": "SEP 2026", "z": 0.3, "source": "FRED"},
        "unrate": {"name": "Unemployment Rate", "value": 4.1, "prev": 4.2, "units": "%", "period": "OCT 2026", "z": -0.3, "source": "FRED"},
        "nfp": {"name": "Non-Farm Payrolls", "value": 165, "prev": 60, "units": "k", "period": "OCT 2026", "z": 0.0, "source": "FRED"},
        "claims": {"name": "Initial Jobless Claims", "value": 200, "prev": 191, "units": "k", "period": "07 NOV 2026", "z": -0.3, "source": "FRED"},
        "fed_funds": {"name": "Fed Funds Upper Target", "value": 4.0, "prev": 4.25, "units": "%", "period": "13 NOV 2026", "z": 0.7, "source": "FRED"},
        "gdp_qoq": {"name": "Real GDP (QoQ SAAR)", "value": 3.4, "prev": 2.2, "units": "%", "period": "Q3 2026", "z": 0.1, "source": "FRED"},
        "hy_oas": {"name": "High-Yield Credit Spread", "value": 3.2, "prev": 3.3, "units": "%", "period": "12 NOV 2026", "z": 0.4, "source": "FRED"},
    },
    "yield_curve": {"asof": "2026-11-12", "source": "FRED", "tenors_pct": {"2Y": 4.86, "10Y": 5.1},
                    "spreads": [{"label": "2s10s", "value_pct": 0.27, "value_bp": 27, "chg_1m_bp": -15}]},
    "uk": {
        "uk_bank_rate": {"name": "Bank Rate", "value": 4.0, "prev": 4.0, "units": "%", "period": "12 NOV 2026", "z": 0.5, "source": "BoE"},
        "uk_cpi_yoy": {"name": "CPI YoY", "value": 3.5, "prev": 3.1, "units": "%", "period": "SEP 2026", "z": 0.6, "source": "ONS"},
    },
    "sentiment": {"vix_term": {"vix": 19.3, "vix3m": 20.6, "ratio": 0.94, "state": "contango", "pctile_1y": 80}},
    "news": [{"id": NEWS_ID, "source": "CNBC", "title": "Wholesale prices rose 0.3% in October, the most in a year"}],
    "regime": {
        "growth_inflation": {"quadrant": "Goldilocks", "label": "Goldilocks", "boundary": False,
                             "allowed_quadrants": ["Goldilocks"],
                             "growth": {"score": 0.7, "state": "accelerating", "components": []},
                             "inflation": {"score": -0.3, "state": "decelerating", "components": []},
                             "core_pce_pct": 3.1, "inflation_target_pct": 2.0},
        "growth_policy": {"label": "Neutral policy, growth rising", "stance": "neutral", "real_rate_pct": 0.75},
        "credit_duration": {"label": "Credit and duration balanced", "leader": "balanced", "score_pp": -0.1, "pairs": []},
        "tendencies": [],
    },
}

BAD = [
    "Core CPI rose to 3.7%.",                      # headline CPI's value under the core label
    "The S&P 500 rose 0.4% on the day.",           # it fell 0.4%
    "The Dow is above 40,000.",                    # invented level (only the DIA return is known)
    "Inflation hit 7%.",                           # 7.0% exists, but as a sector return
    "Claims jumped to 250K.",                      # uppercase suffix, invented
    "Tech fell 9 %.",                              # spaced unit, invented
    "Payrolls rose by two hundred thousand.",      # spelled-out number
    "Unemployment is 4%.",                         # coarser than the digest's 4.1
    "Energy rose 5%.",                             # coarser than 5.4
    "The spread widened 10 bp.",                   # spaced unit, small number
    "Prices fell 1.5pc.",                          # 'pc' suffix; must not truncate to 1
    "Claims were 4,512.5K.",                       # comma + decimals + uppercase K
    "The 10-year yield fell 5bp.",                 # it rose 5bp
    "Wholesale prices rose 0.3% in October.",      # headline number outside news_clusters.summary
    "VIX at 19.3%.",                               # level quoted as a percentage
    "The 2s10s spread is 0.27bp.",                 # pp value with a bp unit
    "Core PCE was 2.6%.",                          # core CPI's value under the core PCE label
    "Bank Rate is 3.7%.",                          # wrong metric
    "The 10-year yield is 4.86%.",                 # that is the 2-year
    "Gold rose 3.2%.",                             # 3.2% is the VIX move; gold was flat
    "The Nasdaq fell -0.4%.",                      # Nasdaq fell 1.2%
    "GDP grew 3%.",                                # coarser than 3.4
    "Payrolls added 1.5 million jobs.",            # spelled scale, invented
    "Unemployment rose to 4.1%.",                  # it fell from 4.2
    "Claims rose to 191k.",                        # 191 is the previous value, not the latest
]

GOOD = [
    "Core CPI rose to 2.6% from 2.4%.",
    "CPI rose to 3.7% from 3.4%.",
    "The S&P 500 fell 0.4%.",
    "The S&P 500 slipped −0.4% on the day while the Nasdaq 100 dropped 1.2%.",
    "Claims rose to 200k from 191k.",
    "Claims were 200,000 last week.",
    "Payrolls rose to 165k.",
    "Unemployment fell to 4.1%.",
    "The 10-year yield rose 5bp to 5.15%.",
    "On the Treasury curve the 10Y yield is 5.1% and the 2-year is 4.86%.",
    "The 2s10s spread is 27bp, 15bp narrower over a month.",
    "VIX rose 3.2% to 19.3.",
    "Energy gained 5.4% over the week; Technology fell 13.2% over the month.",
    "The Russell 2000 slipped 0.3% and the Dow Jones gained 0.1%.",
    "Core PCE inflation is still 3.1% vs the 2% target.",
    "Bank Rate held at 4.0%; UK CPI rose to 3.5%.",
    "Growth score is 0.7 and the inflation score is −0.3.",
    "Fed funds upper bound is 4.0%, down from 4.25%.",
    "Gold was flat at 0.0%.",
    "As of Nov 13, the S&P 500 fell 0.4% over 1D, with 3 sectors up over 1M and 3M.",
    "The high-yield spread narrowed to 3.2%.",
    "Unemployment is 4.1 percent.",
    "The real policy rate is 0.75%.",
]


def out_with(text: str, field: str = "what_moved") -> dict:
    return {
        "brief": {"headline": "Markets mixed", "bullets": ["One.", "Two.", "Three."],
                  "what_moved": "Stocks were mixed.", "cycle_view": "The cycle is unchanged.", field: text},
        "news_clusters": [{"topic": "Prices", "summary": "Producer prices news.", "tags": ["macro"], "item_ids": [NEWS_ID]}],
        "regime_explainer": {"rationale": "Growth is accelerating.", "caveats": ["Data are revised."]},
    }


@pytest.mark.parametrize("text", BAD)
def test_adversarial_rejected(text):
    v = V.validate(out_with(text), DIGEST)
    assert v, f"slipped through: {text!r}"
    assert all("brief.what_moved" in x for x in v)


@pytest.mark.parametrize("text", GOOD)
def test_grounded_accepted(text):
    assert V.validate(out_with(text), DIGEST) == []


def test_headline_numbers_allowed_only_in_cluster_summary():
    out = out_with("Stocks were mixed.")
    out["news_clusters"][0]["summary"] = "Wholesale prices rose 0.3% in October, the most in a year."
    assert V.validate(out, DIGEST) == []


def test_digest_names_and_periods_do_not_whitelist_numbers():
    d = copy.deepcopy(DIGEST)
    d["economy"]["claims"]["period"] = "21 NOV 2026"  # 21 must not become a quotable number
    assert V.validate(out_with("Claims rose 21%."), d)
