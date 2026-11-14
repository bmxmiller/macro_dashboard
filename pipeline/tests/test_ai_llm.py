"""LLM client: provider chain, retries, key handling. Fully offline (http.post is mocked)."""
import json

import pytest
import requests

from pipeline.ai import llm

GEMINI_KEY = "AIzaFAKEFAKEFAKEFAKEFAKEFAKE1234"
GROQ_KEY = "gsk_FAKEFAKEFAKEFAKEFAKEFAKE1234"


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(llm, "_sleep", lambda s: None)


@pytest.fixture
def cfg():
    c = llm.load_config()
    c["retries"] = 1
    # Pin the chain shape the tests exercise (two Gemini models, then Groq) so they don't
    # depend on which models production ai.yaml currently lists.
    c["providers"]["gemini"]["models"] = ["gemini-test-primary", "gemini-test-fallback"]
    return c


@pytest.fixture
def both_keys(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", GEMINI_KEY)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)


class FakeResp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


def http_error(code: int, body: str = "") -> requests.HTTPError:
    r = requests.Response()
    r.status_code = code
    r._content = body.encode()
    return requests.HTTPError(f"{code} error", response=r)


def gemini_ok(data: dict) -> dict:
    return {"candidates": [{"content": {"parts": [{"text": "thinking...", "thought": True},
                                                 {"text": json.dumps(data)}]}}]}


def groq_ok(data: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(data)}}]}


class Recorder:
    """Fake http.post: pops scripted outcomes per host, records calls."""

    def __init__(self, script: dict[str, list]):
        self.script = script
        self.calls: list[dict] = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        host = "gemini" if "googleapis" in url else "groq"
        self.calls.append({"host": host, "url": url, "headers": headers, "body": json})
        outcome = self.script[host].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResp(outcome)


def test_no_keys_raises_no_provider_available(monkeypatch, cfg):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.NoProviderAvailable):
        llm.available_providers(cfg)
    with pytest.raises(llm.NoProviderAvailable):
        llm.generate("s", "p", {}, cfg=cfg)


def test_blank_key_counts_as_unset(monkeypatch, cfg):
    monkeypatch.setenv("GEMINI_API_KEY", "  ")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.NoProviderAvailable):
        llm.available_providers(cfg)


def test_provider_order_is_gemini_then_groq(both_keys, cfg):
    names = [p.name for p in llm.available_providers(cfg)]
    assert names[0] == "gemini" and names[-1] == "groq"


def test_only_groq_key_uses_groq(monkeypatch, cfg):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)
    assert {p.name for p in llm.available_providers(cfg)} == {"groq"}


def test_gemini_success_uses_header_key_and_json_mode(both_keys, cfg, monkeypatch):
    rec = Recorder({"gemini": [gemini_ok({"a": 1})], "groq": []})
    monkeypatch.setattr(llm.http, "post", rec)
    res = llm.generate("sys", "prompt", {"type": "OBJECT"}, cfg=cfg)
    assert res.data == {"a": 1} and res.provider == "gemini"
    call = rec.calls[0]
    assert GEMINI_KEY not in call["url"]  # key never in the URL
    assert call["headers"]["x-goog-api-key"] == GEMINI_KEY
    gen = call["body"]["generationConfig"]
    assert gen["responseMimeType"] == "application/json" and gen["responseSchema"] == {"type": "OBJECT"}


def test_fallback_order_on_failures(both_keys, cfg, monkeypatch):
    # primary gemini: 400 (no retry) → gemini lite: 429 twice (retried, then give up) → groq ok
    rec = Recorder({"gemini": [http_error(400), http_error(429), http_error(503)], "groq": [groq_ok({"ok": True})]})
    monkeypatch.setattr(llm.http, "post", rec)
    res = llm.generate("sys", "prompt", {}, cfg=cfg)
    assert res.provider == "groq" and res.data == {"ok": True}
    models = [c["body"].get("model") or c["url"].split("/models/")[1].split(":")[0] for c in rec.calls]
    p = llm.configured_providers(cfg)
    assert models == [p[0].model, p[1].model, p[1].model, p[2].model]
    assert rec.calls[-1]["headers"]["Authorization"] == f"Bearer {GROQ_KEY}"
    assert rec.calls[-1]["body"]["response_format"] == {"type": "json_object"}


def test_bad_json_is_retried(both_keys, cfg, monkeypatch):
    bad = {"candidates": [{"content": {"parts": [{"text": "not json"}]}}]}
    rec = Recorder({"gemini": [bad, gemini_ok({"x": 2})], "groq": []})
    monkeypatch.setattr(llm.http, "post", rec)
    assert llm.generate("s", "p", {}, cfg=cfg).data == {"x": 2}
    assert len(rec.calls) == 2


def test_all_fail_raises_redacted_error(both_keys, cfg, monkeypatch):
    leak = http_error(401, f'{{"error": "API key {GEMINI_KEY} invalid"}}')
    rec = Recorder({"gemini": [leak, leak], "groq": [http_error(401, f"Bearer {GROQ_KEY}")]})
    monkeypatch.setattr(llm.http, "post", rec)
    with pytest.raises(llm.LLMError) as ei:
        llm.generate("s", "p", {}, cfg=cfg)
    assert not isinstance(ei.value, llm.NoProviderAvailable)
    msg = str(ei.value)
    assert GEMINI_KEY not in msg and GROQ_KEY not in msg and "HTTP 401" in msg


def test_redact_covers_llm_keys():
    from pipeline.fetchers.http import redact
    for text in (f"Authorization: Bearer {GROQ_KEY}", f'{{"x-goog-api-key": "{GEMINI_KEY}"}}',
                 f"key {GEMINI_KEY} invalid", f"https://x/y?key={GEMINI_KEY}"):
        out = redact(text)
        assert GEMINI_KEY not in out and GROQ_KEY not in out


def test_only_groq_key_end_to_end_never_calls_gemini(monkeypatch, cfg, caplog):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", GROQ_KEY)
    rec = Recorder({"gemini": [], "groq": [groq_ok({"ok": 1})]})  # any gemini call would IndexError
    monkeypatch.setattr(llm.http, "post", rec)
    with caplog.at_level("INFO", logger="ai.llm"):
        res = llm.generate("s", "p", {}, cfg=cfg)
    assert res.provider == "groq" and res.data == {"ok": 1}
    assert [c["host"] for c in rec.calls] == ["groq"]
    assert all(r.levelname == "INFO" for r in caplog.records)  # skipping gemini is not a warning
    assert any("skipped (no key): gemini" in r.getMessage() for r in caplog.records)


def test_order_is_configurable(both_keys, cfg):
    cfg["order"] = ["groq", "gemini"]
    names = [p.name for p in llm.available_providers(cfg)]
    assert names == sorted(names, key=lambda n: n != "groq") and names[0] == "groq" and names[-1] == "gemini"


def test_redact_masks_env_key_values_of_any_format(monkeypatch):
    from pipeline.fetchers.http import redact
    odd = "AQ.Ab8RN6FAKEfakeFAKEfake"  # newer Gemini key prefix, matches no regex
    monkeypatch.setenv("GEMINI_API_KEY", odd)
    assert odd not in redact(f"error: bad credential {odd}")
