"""Shared HTTP session with retries and a polite, generic User-Agent."""
from __future__ import annotations

import logging
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


def redact(text: str) -> str:
    """Strip secret query parameters (e.g. FRED api_key) from URLs inside messages.
    requests embeds the full URL in HTTPError/RetryError text, and those messages
    end up in logs and in the public meta.json."""
    return _SECRET_PARAM.sub(r"\1***", text)


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
