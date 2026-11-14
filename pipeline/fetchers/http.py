"""Shared HTTP session with retries and a polite, generic User-Agent."""
from __future__ import annotations

import logging
import os
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504))
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.mount("http://", HTTPAdapter(max_retries=retry))
        # Plain, honest client name. FRED stalls requests that pose as a browser.
        s.headers["User-Agent"] = "macro-dashboard/0.1 python-requests"
        _session = s
    return _session


_SECRET_PARAM = re.compile(r"((?:api_key|apikey|key|token)=)[^&\s'\"]+", re.IGNORECASE)


# Header-style and bare credentials. LLM keys travel in headers, but be safe if one
# is ever echoed back in an error body: "Bearer …", "x-goog-api-key: …",
# Google API keys (AIza…) and Groq keys (gsk_…).
_SECRET_HEADER = re.compile(
    r"((?:Bearer|x-goog-api-key[\"']?\s*[:=])\s*[\"']?)[A-Za-z0-9._\-]{8,}", re.IGNORECASE)
_SECRET_ENV = ("FRED_API_KEY", "GEMINI_API_KEY", "GROQ_API_KEY")
_SECRET_BARE = re.compile(r"\b(?:AIza[0-9A-Za-z_\-]{20,}|gsk_[0-9A-Za-z]{20,})")


def redact(text: str) -> str:
    """Strip secret query parameters (e.g. FRED api_key) from URLs inside messages.
    requests embeds the full URL in HTTPError/RetryError text, and those messages
    end up in logs and in the public meta.json. Also masks bearer tokens and
    Gemini/Groq-style keys in case an error body echoes one."""
    text = _SECRET_PARAM.sub(r"\1***", text)
    text = _SECRET_HEADER.sub(r"\1***", text)
    text = _SECRET_BARE.sub("***", text)
    # Key formats change (Gemini keys may start "AQ." instead of "AIza"), so also mask the
    # literal values of the configured secret env vars, whatever they look like.
    for var in _SECRET_ENV:
        val = os.environ.get(var, "").strip()
        if len(val) >= 8:
            text = text.replace(val, "***")
    return text


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def get(url: str, **kw) -> requests.Response:
    kw.setdefault("timeout", 30)
    r = session().get(url, **kw)
    r.raise_for_status()
    return r


def post(url: str, **kw) -> requests.Response:
    """POST through the shared session. urllib3's Retry does not retry POST (not
    idempotent), so callers that want retries (pipeline/ai/llm.py) do their own."""
    kw.setdefault("timeout", 30)
    r = session().post(url, **kw)
    r.raise_for_status()
    return r


# Some public hosts (BoE, CNN, CNBC, Yahoo RSS) reject non-browser clients.
# Pass these per request (``get(url, headers=browser_headers())``); never change
# the session default, because FRED/BLS stall or block browser-like UAs.
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def browser_headers(**extra: str) -> dict[str, str]:
    h = {"User-Agent": _BROWSER_UA, "Accept": "*/*", "Accept-Language": "en-GB,en;q=0.9"}
    h.update(extra)
    return h
