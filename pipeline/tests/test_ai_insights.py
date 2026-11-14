"""Insights flow (LLM mocked): retry with feedback, provider fallback, skip without keys, size bound."""
import json
import shutil
from pathlib import Path

import pytest

from pipeline import build
from pipeline.ai import context, insights, llm
from pipeline.ai.regime import compute_regime
from pipeline.schemas import Insights

DATA = Path(__file__).resolve().parents[2] / "web" / "public" / "data"
INPUTS = ["markets", "economy", "yield_curve", "uk", "sentiment", "positioning", "news"]


@pytest.fixture
def data_dir(tmp_path):
    for n in INPUTS + ["meta"]:
        shutil.copy(DATA / f"{n}.json", tmp_path / f"{n}.json")
    return tmp_path


@pytest.fixture
def keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaFAKEFAKEFAKEFAKEFAKEFAKE1234")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_FAKEFAKEFAKEFAKEFAKEFAKE1234")


def first_news_id(d: Path) -> str:
    return context.news_digest(json.loads((d / "news.json").read_text(encoding="utf-8")))[0]["id"]


def answer(news_id: str, extra: str = "") -> dict:
    return {
        "brief": {"headline": "Growth firm, inflation steady" + extra,
                  "bullets": ["Growth indicators improved.", "Core inflation was little changed.", "Volatility is moderate."],
                  "what_moved": "Sector leadership rotated over the week.",
                  "cycle_view": "Rules place the economy in the quadrant shown."},
        "news_clusters": [{"topic": "Markets", "summary": "Headlines on stocks.", "tags": ["equities"],
                           "item_ids": [news_id]}],
        "regime_explainer": {"rationale": "Growth score positive.", "asset_tendencies": ["Equities historically did well."],
                             "caveats": ["Data are revised."]},
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
    nid = first_news_id(data_dir)
    fake = ScriptedLLM([answer(nid)])
    monkeypatch.setattr(insights.llm, "generate", fake)
    out = insights.build_insights(data_dir)
    assert isinstance(out, Insights) and len(fake.calls) == 1
    assert out.provider == "gemini" and out.disclaimer.startswith("AI-generated")
    assert out.news_clusters[0].items[0].url.startswith("http")  # ids resolved to links
    assert out.regime.growth_inflation.quadrant is not None      # code-computed regime attached
    assert out.regime.explainer.rationale == "Growth score positive."


def test_retry_with_feedback_then_accept(data_dir, keys, monkeypatch):
    nid = first_news_id(data_dir)
    fake = ScriptedLLM([answer(nid, extra=" as GDP hits 9.87%"), answer(nid)])
    monkeypatch.setattr(insights.llm, "generate", fake)
    out = insights.build_insights(data_dir)
    assert len(fake.calls) == 2 and fake.calls[0]["provider"] == fake.calls[1]["provider"]
    assert "REJECTED" not in fake.calls[0]["prompt"]
    assert "REJECTED" in fake.calls[1]["prompt"] and '"9.87%"' in fake.calls[1]["prompt"]
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


def test_no_keys_raises_before_any_call(data_dir, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(insights.llm, "generate", lambda *a, **k: pytest.fail("must not call the LLM"))
    with pytest.raises(llm.NoProviderAvailable):
        insights.build_insights(data_dir)


def test_context_size_bound(data_dir):
    d = context.build_digest(data_dir, compute_regime(context.load(data_dir, "economy"), context.load(data_dir, "markets")))
    assert context.approx_tokens(d) < 6000
    assert len(d["news"]) <= context.MAX_HEADLINES
    for panel in d["markets"].values():
        if isinstance(panel, dict):
            assert all(len(panel[p]["top"]) <= 3 and len(panel[p]["bottom"]) <= 3 for p in ("1W", "1M"))
    assert set(d) >= {"markets", "economy", "yield_curve", "uk", "sentiment", "positioning_extremes", "news", "regime"}


def test_build_skips_cleanly_without_keys(data_dir, monkeypatch):
    monkeypatch.setattr(build, "OUT", data_dir)
    monkeypatch.setattr(build, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    (data_dir / "insights.json").write_text('{"previous": true}', encoding="utf-8")
    assert build.main(["--only", "insights"]) == 0
    assert json.loads((data_dir / "insights.json").read_text()) == {"previous": True}  # untouched
    meta = json.loads((data_dir / "meta.json").read_text())["sections"]["insights"]
    assert meta["ok"] is True and meta["skipped"] is True and "GEMINI_API_KEY" in meta["note"]


def test_build_failure_keeps_previous_and_flags_stale(data_dir, keys, monkeypatch):
    monkeypatch.setattr(build, "OUT", data_dir)
    monkeypatch.setattr(build, "load_dotenv", lambda: None)
    monkeypatch.setattr(insights.llm, "generate", ScriptedLLM([llm.LLMError("down")] * 3))
    (data_dir / "insights.json").write_text('{"previous": true}', encoding="utf-8")
    assert build.main(["--only", "insights"]) == 1
    assert json.loads((data_dir / "insights.json").read_text()) == {"previous": True}
    assert json.loads((data_dir / "meta.json").read_text())["sections"]["insights"]["ok"] is False


def test_etf_proxy_prices_not_in_digest(data_dir):
    snap = context.build_digest(data_dir)["markets"]["index_snapshot_1D"]
    by = {r["tag"]: r for r in snap}
    assert "level" not in by["SPY"] and "level" in by["INDEX"]  # SPY price ≠ S&P 500 level; VIX is a level
