"""RSS headlines from free official and public feeds (feedparser, no key).

Pure helpers (strip_html, normalize_title, tag_text, parse_feed, select_items)
are kept separate from network code so they can be unit-tested.
"""
from __future__ import annotations

import calendar
import hashlib
import html
import re
from datetime import datetime, timedelta, timezone

import feedparser

from .http import browser_headers, get

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None, limit: int = 280) -> str:
    """Remove tags/entities, collapse whitespace and truncate on a word boundary."""
    if not text:
        return ""
    t = _TAG_RE.sub(" ", text)
    t = _WS_RE.sub(" ", html.unescape(t)).strip()
    if len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return t


def normalize_title(title: str) -> str:
    """Lowercase, unify quotes/dashes, drop punctuation: used as the dedupe key."""
    t = html.unescape(title or "").lower()
    t = re.sub(r"[‘’“”'\"`]", "", t)
    t = re.sub(r"[^a-z0-9&%$ ]+", " ", t)
    return _WS_RE.sub(" ", t).strip()


def compile_rules(rules: dict[str, list[str]]) -> dict[str, re.Pattern]:
    out = {}
    for tag, words in rules.items():
        alts = sorted({re.escape(w.lower()) for w in words}, key=len, reverse=True)
        # (?<![\w&]) / (?![\w&]) act as word boundaries that also work for "s&p".
        out[tag] = re.compile(r"(?<![\w&])(?:" + "|".join(alts) + r")(?![\w&])", re.IGNORECASE)
    return out


def tag_text(text: str, compiled: dict[str, re.Pattern], base: list[str] | None = None) -> list[str]:
    tags = list(dict.fromkeys(base or []))
    for tag, rx in compiled.items():
        if tag not in tags and rx.search(text or ""):
            tags.append(tag)
    order = list(compiled)  # stable order: registry order, base-only tags last
    return sorted(tags, key=lambda t: order.index(t) if t in order else len(order))


def _entry_time(e) -> datetime | None:
    st = e.get("published_parsed") or e.get("updated_parsed")
    if not st:
        return None
    return datetime.fromtimestamp(calendar.timegm(st), tz=timezone.utc)


def parse_feed(content: bytes | str, feed: dict, compiled: dict[str, re.Pattern]) -> list[dict]:
    parsed = feedparser.parse(content)
    items = []
    for e in parsed.entries:
        title = strip_html(e.get("title"), limit=300)
        url = e.get("link")
        ts = _entry_time(e)
        if not title or not url or ts is None:
            continue
        summary = strip_html(e.get("summary") or e.get("description"))
        if normalize_title(summary) == normalize_title(title):
            summary = ""
        tags = tag_text(f"{title} {summary}", compiled, feed.get("tags"))
        if feed.get("require_tags") and not tags:
            continue  # general-news feeds: skip stories with no market/macro keyword
        items.append({
            "id": hashlib.sha1(normalize_title(title).encode()).hexdigest()[:12],
            "title": title,
            "url": url,
            "source": feed["source"],
            "feed": feed["id"],
            "published": ts.replace(microsecond=0).isoformat(),
            "summary": summary,
            "tags": tags,
        })
    return items


def select_items(items: list[dict], now: datetime, window_hours: int, max_items: int,
                 max_per_feed: int) -> list[dict]:
    """Window filter -> dedupe by normalized title (first feed wins) -> per-feed cap -> newest first."""
    cutoff = now - timedelta(hours=window_hours)
    seen, per_feed, out = set(), {}, []
    for it in items:
        ts = datetime.fromisoformat(it["published"])
        if ts < cutoff or ts > now + timedelta(hours=1):
            continue
        key = normalize_title(it["title"])
        if key in seen:
            continue
        seen.add(key)
        per_feed.setdefault(it["feed"], []).append(it)
    for lst in per_feed.values():
        lst.sort(key=lambda x: x["published"], reverse=True)
        out += lst[:max_per_feed]
    out.sort(key=lambda x: x["published"], reverse=True)
    return out[:max_items]


def fetch_feed(feed: dict) -> bytes:
    hdr = {"Accept": "application/rss+xml, application/xml, text/xml, */*"}
    if feed.get("browser"):
        hdr = browser_headers(**hdr)
    return get(feed["url"], headers=hdr, timeout=20).content
