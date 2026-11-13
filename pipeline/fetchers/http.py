"""Shared HTTP session with retries and a polite, generic User-Agent."""
from __future__ import annotations

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


def get(url: str, **kw) -> requests.Response:
    kw.setdefault("timeout", 30)
    r = session().get(url, **kw)
    r.raise_for_status()
    return r
