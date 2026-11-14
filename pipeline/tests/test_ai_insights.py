"""Insights + regime sections (LLM mocked): retry with feedback, fallback, skip, size bound."""
import json
import shutil
from pathlib import Path

import pytest

from pipeline import build
from pipeline.ai import context, insights, llm
from pipeline.ai.regime import compute_regime
from pipeline.schemas import Insights

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"


@pytest.fixture
def data_dir(tmp_path):
    for n in list(context.INPUTS) + ["meta"]:
        shutil.copy(DATA / f"{n}.json", tmp_path / f"{n}.json")
    return tmp_path


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFAKEFAKEFAKEFAKEFAKEFAKE1234")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_FAKEFAKEFAKEFAKEFAKEFAKE1234")


@pytest.fixture
def no_keys(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)


@pytest.fixture
def isolated_build(data_dir, monkeypatch):
    monkeypatch.setattr(build, "OUT", data_dir)
    monkeypatch.setattr(build, "load_dotenv", lambda: None)
    return data_dir


def first_news_id(d: Path) -> str:
    return context.news_digest(json.loads((d / "news.json").read_text(encoding="utf-8")))[0]["id"]


def answer(news_id: str, extra: str = "") -> dict:
    return {
        "brief": {"headline": "Markets mixed as data firm" + extra,
                  "bullets": ["Growth indicators improved.", "Core inflation was little changed.", "Volatility is moderate."],
                  "what_moved": "Sector leadership rotated over the week.",
                  "cycle_view": "The rules place the economy in the regime shown in the panel."},
        "news_clusters": [{"topic": "Markets", "summary": "Headlines on stocks.", "tags": ["equities"],
                           "item_ids": [news_id]}],
        "regime_explainer": {"rationale": "The growth signal is positive.", "caveats": ["Data are revised."]},
    }


class ScriptedLLM:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, system, prompt, schema, *, providers=None, cfg=None):
        self.calls.append({"provider": providers[0].label, "prompt": prompt})
        o = self.outcomes.pop(0)
        if isinstance(o, Exception):
            raise o
        return llm.LLMResult(data=o, provider=providers[0].name, model=providers[0].model)


def test_happy_path_one_call(data_dir, keys, monkeypatch):
    fake = ScriptedLLM([answer(first_news_id(data_dir))])
    monkeypatch.setattr(insights.llm, "generate", fake)
    out = insights.build_insights(data_dir)
    assert isinstance(out, Insights) and len(fake.calls) == 1
    assert out.provider == "gemini" and out.disclaimer.startswith("AI-generated")
    assert out.news_clusters[0].items[0].url.startswith("http")  # ids resolved to links
    assert out.regime_explainer.rationale == "The growth signal is positive."
    assert out.regime_explainer.regime_label  # references the regime it explained
    assert "regime" not in out.model_dump()   # the regime itself lives in regime.json
    assert any("validate.py" in s["url"] for s in out.sources)


def test_explainer_references_published_regime(isolated_build, keys, monkeypatch):
    assert build.main(["--only", "regime"]) == 0
    reg = json.loads((isolated_build / "regime.json").read_text())
    monkeypatch.setattr(insights.llm, "generate", ScriptedLLM([answer(first_news_id(isolated_build))]))
    out = insights.build_insights(isolated_build)
    assert out.regime_explainer.regime_generated_at == reg["generated_at"]
    assert out.regime_explainer.regime_label == reg["growth_inflation"]["label"]


def test_retry_with_feedback_then_accept(data_dir, keys, monkeypatch):
    nid = first_news_id(data_dir)
    fake = ScriptedLLM([answer(nid, extra=" as GDP hits 9.87%"), answer(nid)])
    monkeypatch.setattr(insights.llm, "generate", fake)
    out = insights.build_insights(data_dir)
    assert len(fake.calls) == 2 and fake.calls[0]["provider"] == fake.calls[1]["provider"]
    assert "REJECTED" not in fake.calls[0]["prompt"]
    assert "REJECTED" in fake.calls[1]["prompt"] and "9.87%" in fake.calls[1]["prompt"]
    assert "9.87" not in out.brief.headline


def test_falls_back_to_next_provider_after_two_rejections(data_dir, keys, monkeypatch):
    nid = first_news_id(data_dir)
    bad = answer(nid, extra=" (+42.42%)")
    fake = ScriptedLLM([bad, bad, answer(nid)])
    monkeypatch.setattr(insights.llm, "generate", fake)
    out = insights.build_insights(data_dir)
    assert [c["provider"] for c in fake.calls][:2] == [fake.calls[0]["provider"]] * 2
    assert fake.calls[2]["provider"] != fake.calls[0]["provider"]
    assert out.model == llm.configured_providers(llm.load_config())[1].model


def test_provider_error_moves_on_and_all_failing_raises(data_dir, keys, monkeypatch):
    nid = first_news_id(data_dir)
    bad = answer(nid, extra=" (+42.42%)")
    n = len(llm.configured_providers(llm.load_config()))
    # first provider errors (1 call), every other provider is rejected twice (2 calls each)
    fake = ScriptedLLM([llm.LLMError("HTTP 500")] + [bad] * (2 * (n - 1)))
    monkeypatch.setattr(insights.llm, "generate", fake)
    with pytest.raises(insights.InsightsError):
        insights.build_insights(data_dir)
    assert len(fake.calls) == 1 + 2 * (n - 1)


def test_unknown_news_id_is_rejected(data_dir, keys, monkeypatch):
    fake = ScriptedLLM([answer("not-a-real-id"), answer(first_news_id(data_dir))])
    monkeypatch.setattr(insights.llm, "generate", fake)
    insights.build_insights(data_dir)
    assert "not-a-real-id" in fake.calls[1]["prompt"]


def test_no_keys_raises_before_any_call(data_dir, no_keys, monkeypatch):
    monkeypatch.setattr(insights.llm, "generate", lambda *a, **k: pytest.fail("must not call the LLM"))
    with pytest.raises(llm.NoProviderAvailable):
        insights.build_insights(data_dir)


def test_context_size_bound_and_units(data_dir):
    inputs = context.load_inputs(data_dir)
    d = context.build_digest(inputs, compute_regime(inputs["economy"], inputs["markets"]))
    assert context.approx_tokens(d) < 6000
    assert len(d["news"]) <= context.MAX_HEADLINES
    for name, panel in d["markets"].items():
        if name == "index_snapshot":
            continue
        for p in ("1W", "1M"):
            assert len(panel[p]["top"]) <= 3 and len(panel[p]["bottom"]) <= 3
            assert all(("ret_pct" in r) != ("chg_bp" in r) for r in panel[p]["top"])  # unit in the key
    assert set(d) >= {"markets", "economy", "yield_curve", "uk", "sentiment", "positioning_extremes", "news", "regime"}
    comp = d["regime"]["growth_inflation"]["growth"]["components"]
    assert all(any(k.endswith(("_pct", "_pp", "_k")) for k in c) for c in comp)


def test_duplicated_values_carry_source(data_dir):
    d = context.build_digest(context.load_inputs(data_dir))
    assert d["economy"]["vix"]["source"] == "FRED" and "Yahoo" in d["sentiment"]["vix_term"]["source"]
    assert d["yield_curve"]["source"].startswith("FRED")
    assert all(r["source"] == "Yahoo Finance" and r["asof"] for r in d["markets"]["index_snapshot"])


def test_etf_proxy_prices_not_in_digest(data_dir):
    by = {r["tag"]: r for r in context.build_digest(context.load_inputs(data_dir))["markets"]["index_snapshot"]}
    assert "level" not in by["SPY"] and "level" in by["INDEX"]  # SPY price ≠ S&P 500 level; VIX is a level


@pytest.mark.parametrize("net,pct,text", [
    (1000, 95, "most net long in 3y"), (-1000, 95, "least net short in 3y"),
    (-1000, 5, "most net short in 3y"), (1000, 5, "least net long in 3y"),
])
def test_positioning_text_is_sign_aware(net, pct, text):
    assert context.position_text(net, pct) == text


def test_regime_section_runs_without_keys(isolated_build, no_keys):
    assert build.main(["--only", "regime"]) == 0
    reg = json.loads((isolated_build / "regime.json").read_text())
    assert reg["growth_inflation"]["label"] and reg["methodology_url"].endswith("regime.py")
    assert reg["tendencies"]["basis"].startswith("Greetham & Hartnett")
    assert reg["sources"] and all(s["url"].startswith("http") for s in reg["sources"])
    assert json.loads((isolated_build / "meta.json").read_text())["sections"]["regime"]["ok"] is True


def test_regime_runs_before_insights_whatever_the_order(isolated_build, no_keys, monkeypatch):
    order = []
    monkeypatch.setattr(build, "build_regime", lambda out: order.append("regime") or {"generated_at": "x"})
    monkeypatch.setattr(build, "build_insights", lambda out: order.append("insights") or {"generated_at": "x"})
    build.main(["--only", "insights", "regime"])
    assert order == ["regime", "insights"]


def test_build_skips_cleanly_without_keys(isolated_build, no_keys):
    (isolated_build / "insights.json").write_text('{"previous": true}', encoding="utf-8")
    assert build.main(["--only", "insights"]) == 0
    assert json.loads((isolated_build / "insights.json").read_text()) == {"previous": True}  # untouched
    meta = json.loads((isolated_build / "meta.json").read_text())["sections"]["insights"]
    assert meta["ok"] is True and meta["skipped"] is True and "GEMINI_API_KEY" in meta["note"]


def test_build_failure_keeps_previous_and_flags_stale(isolated_build, keys, monkeypatch):
    monkeypatch.setattr(insights.llm, "generate", ScriptedLLM([llm.LLMError("down")] * 4))
    (isolated_build / "insights.json").write_text('{"previous": true}', encoding="utf-8")
    assert build.main(["--only", "insights"]) == 1
    assert json.loads((isolated_build / "insights.json").read_text()) == {"previous": True}
    assert json.loads((isolated_build / "meta.json").read_text())["sections"]["insights"]["ok"] is False
