"""Thin JSON-only LLM client over free tiers: Gemini (primary) → Groq (fallback).

    generate(system, prompt, schema) -> LLMResult(data, provider, model)

* Providers and models come from ``registry/ai.yaml``; a provider is used only when
  its key env var (GEMINI_API_KEY / GROQ_API_KEY) is set. No keys → NoProviderAvailable.
* Keys travel in headers only (``x-goog-api-key`` / ``Authorization: Bearer``), never in
  URLs, and every error message passes through ``redact()`` before it is raised.
* Each provider gets ``retries`` extra attempts on transient failures (429, 5xx,
  timeouts, unparsable JSON); other errors (400/401/403) move straight to the next one.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

from ..fetchers import http
from ..fetchers.http import redact

log = logging.getLogger("ai.llm")

CONFIG_PATH = Path(__file__).resolve().parents[1] / "registry" / "ai.yaml"
_sleep = time.sleep  # monkeypatched in tests


class LLMError(RuntimeError):
    """A provider call failed (message already redacted)."""


class NoProviderAvailable(LLMError):
    """No LLM API key is configured: the AI section should be skipped, not failed."""


class _Transient(LLMError):
    """Worth retrying on the same provider."""

    def __init__(self, msg: str, retry_after: float | None = None):
        super().__init__(msg)
        self.retry_after = retry_after  # seconds the provider asked us to wait (429), if it said


_RETRY_HINT = re.compile(r"try again in\s+(?:(\d+(?:\.\d+)?)m)?\s*(?:(\d+(?:\.\d+)?)s)?", re.IGNORECASE)
MAX_WAIT_S = 65.0  # never sleep longer than this for one retry (a TPM window is 60 s)


def retry_after_seconds(text: str, header: str | None = None) -> float | None:
    """Seconds to wait, from a Retry-After header or Groq's "Please try again in 1m3.2s" text."""
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    m = _RETRY_HINT.search(text)
    if m and (m.group(1) or m.group(2)):
        return float(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    return None


@dataclass(frozen=True)
class ProviderSpec:
    name: str            # "gemini" | "groq"
    model: str
    key_env: str
    response_schema: bool = False

    @property
    def label(self) -> str:
        return f"{self.name}/{self.model}"


@dataclass
class LLMResult:
    data: dict
    provider: str
    model: str


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def configured_providers(cfg: dict) -> list[ProviderSpec]:
    """Every (provider, model) pair in ``order``, keys or not."""
    out = []
    for name in cfg["order"]:
        p = cfg["providers"][name]
        out += [ProviderSpec(name, m, p["key_env"], bool(p.get("response_schema", False))) for m in p["models"]]
    return out


def available_providers(cfg: dict | None = None) -> list[ProviderSpec]:
    """Configured providers whose key env var is set, in ``order``. Others are skipped (info log)."""
    cfg = cfg or load_config()
    out, skipped = [], []
    for spec in configured_providers(cfg):
        if os.environ.get(spec.key_env, "").strip():
            out.append(spec)
        elif spec.name not in skipped:
            skipped.append(spec.name)
    if not out:
        envs = sorted({cfg["providers"][n]["key_env"] for n in cfg["order"]})
        raise NoProviderAvailable(f"no LLM API key set ({' / '.join(envs)})")
    if skipped:
        log.info("LLM providers skipped (no key): %s", ", ".join(skipped))
    return out


# ── Provider adapters ──────────────────────────────────────────────────────

def _post_json(url: str, headers: dict, body: dict, timeout: float) -> dict:
    try:
        r = http.post(url, headers=headers, json=body, timeout=timeout)
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else 0
        detail = ""
        if e.response is not None:
            detail = e.response.text[:300].replace("\n", " ")
        msg = redact(f"HTTP {code}: {detail}")
        if code == 429 or code >= 500:
            hdr = e.response.headers.get("retry-after") if e.response is not None else None
            raise _Transient(msg, retry_after_seconds(detail, hdr) if code == 429 else None) from None
        raise LLMError(msg) from None
    except (requests.Timeout, requests.ConnectionError) as e:
        raise _Transient(redact(f"{type(e).__name__}: {e}")) from None
    try:
        return r.json()
    except ValueError:
        raise _Transient("provider returned non-JSON HTTP body") from None


def _parse_json_text(text: str) -> dict:
    t = text.strip()
    if t.startswith("```"):  # tolerate fenced output
        t = t.strip("`")
        t = t[t.find("{"):]
    try:
        data = json.loads(t)
    except ValueError:
        raise _Transient("model output was not valid JSON") from None
    if not isinstance(data, dict):
        raise _Transient("model output was not a JSON object")
    return data


def call_gemini(spec: ProviderSpec, system: str, prompt: str, schema: dict, cfg: dict) -> dict:
    url = cfg["endpoints"]["gemini"].format(model=spec.model)
    gen = {
        "temperature": cfg["temperature"],
        "maxOutputTokens": cfg["max_output_tokens"],
        "responseMimeType": "application/json",
    }
    if spec.response_schema and schema:
        gen["responseSchema"] = schema
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": gen,
    }
    headers = {"x-goog-api-key": os.environ[spec.key_env].strip(), "Content-Type": "application/json"}
    resp = _post_json(url, headers, body, cfg["timeout_seconds"])
    cands = resp.get("candidates") or []
    if not cands:
        reason = (resp.get("promptFeedback") or {}).get("blockReason", "no candidates")
        raise _Transient(f"gemini returned no output ({reason})")
    parts = (cands[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text:
        raise _Transient(f"gemini returned empty text (finishReason={cands[0].get('finishReason')})")
    return _parse_json_text(text)


def call_groq(spec: ProviderSpec, system: str, prompt: str, schema: dict, cfg: dict) -> dict:
    # json_object mode does not enforce a schema, so describe it in the system prompt
    # (it also requires the word "JSON" to appear in the messages).
    sys_msg = system + "\n\nReturn ONLY a JSON object matching this JSON schema:\n" + json.dumps(schema)
    body = {
        "model": spec.model,
        "messages": [{"role": "system", "content": sys_msg}, {"role": "user", "content": prompt}],
        "temperature": cfg["temperature"],
        "max_tokens": min(cfg["max_output_tokens"], 8192),
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {os.environ[spec.key_env].strip()}", "Content-Type": "application/json"}
    resp = _post_json(cfg["endpoints"]["groq"], headers, body, cfg["timeout_seconds"])
    try:
        text = resp["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        raise _Transient("groq returned an unexpected response shape") from None
    return _parse_json_text(text)


ADAPTERS = {"gemini": call_gemini, "groq": call_groq}


# ── Public entry point ─────────────────────────────────────────────────────

def generate(system: str, prompt: str, schema: dict, *,
             providers: list[ProviderSpec] | None = None, cfg: dict | None = None) -> LLMResult:
    """One JSON completion. Tries each provider in order (with retries) until one answers."""
    cfg = cfg or load_config()
    chain = providers if providers is not None else available_providers(cfg)
    if not chain:
        raise NoProviderAvailable("no LLM provider to try")
    errors: list[str] = []
    for spec in chain:
        adapter = ADAPTERS.get(spec.name)
        if adapter is None:
            errors.append(f"{spec.label}: unknown provider")
            continue
        delay = float(cfg.get("retry_backoff_seconds", 4))
        for attempt in range(int(cfg.get("retries", 2)) + 1):
            try:
                data = adapter(spec, system, prompt, schema, cfg)
                return LLMResult(data=data, provider=spec.name, model=spec.model)
            except _Transient as e:
                msg = redact(str(e))
                log.warning("%s attempt %d failed: %s", spec.label, attempt + 1, msg)
                if attempt < int(cfg.get("retries", 2)):
                    # honour the provider's own hint (Groq asks ~50 s) instead of a 4 s guess
                    wait = min(e.retry_after + 1, MAX_WAIT_S) if e.retry_after else delay
                    _sleep(max(wait, delay))
                    delay *= 2
                else:
                    errors.append(f"{spec.label}: {msg}")
            except LLMError as e:
                msg = redact(str(e))
                log.warning("%s failed: %s", spec.label, msg)
                errors.append(f"{spec.label}: {msg}")
                break
            except Exception as e:  # noqa: BLE001 - never let a raw error (maybe with a URL) escape
                msg = redact(f"{type(e).__name__}: {e}")
                log.warning("%s failed: %s", spec.label, msg)
                errors.append(f"{spec.label}: {msg}")
                break
    raise LLMError("all LLM providers failed: " + " | ".join(errors))
