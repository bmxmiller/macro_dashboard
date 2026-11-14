"""Grounded-number check: every number the LLM writes must exist in its input digest.

Approach
* The *allowed* set is built by walking the digest: numeric values directly, plus every
  number parsed (with the same extractor) out of its strings (names like "S&P 500",
  headlines, period labels). Keys that are ids / dates are skipped.
* Each number in the model's text fields is parsed with its sign, thousands commas,
  decimals and unit suffix (%, bp, pp, k, m, bn, x, "basis points", "percent"…).
* A claim matches if |claim| is within half a unit of its last written decimal of some
  |allowed| value (so "3%" may round 2.6–3.4, but "2.59%" must be 2.585–2.595). Signs are
  compared on magnitude because prose says "fell 3.0%" for −3.0. The only unit
  conversion: plain numbers ≥ 1,000 may match a digest value in k/m ("200,000" ↔ 200k).
  bp and % are not inter-converted (too many false matches); the digest gives spreads in both.
* Exempt: unit-less small integers 0–12 (counts, "3 sectors", "6 months") and years
  1900–2100.
* Numbers glued to letters (10Y, 2s10s, Q3, VIX9D) are labels, not claims, and are ignored.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

# k/m/bn are lowercase-only so period labels like "3M" / "1M" stay labels (ignored).
_SUFFIX = (r"%|bps?\b|pp\b|(?-i:k|m|bn|tn|x)\b|"
           r"\s(?:basis points?|percentage points?|percent|per cent)\b")
NUMBER = re.compile(
    r"(?<![A-Za-z0-9_.,])"              # not glued to a word or another number
    r"([+\-−–]?)\s?[$£€]?"              # optional sign, currency
    r"(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?"
    r"(" + _SUFFIX + r")?"
    r"(?![A-Za-z0-9])", re.IGNORECASE)

SKIP_KEYS = {"id", "item_ids", "asof", "date", "published", "url"}


def extract(text: str) -> list[dict]:
    """[{value, decimals, unit, raw}] for every numeric claim in `text`."""
    out = []
    for m in NUMBER.finditer(text):
        sign, whole, frac, unit = m.groups()
        v = float(whole.replace(",", "") + ("." + frac if frac else ""))
        if sign in ("-", "−", "–"):
            v = -v
        u = (unit or "").strip().lower()
        if u.startswith("basis") or u.startswith("bp"):
            u = "bp"
        elif u.startswith("percentage"):
            u = "pp"
        elif u.startswith("per"):
            u = "%"
        out.append({"value": v, "decimals": len(frac) if frac else 0, "unit": u, "raw": m.group(0).strip()})
    return out


def allowed_numbers(digest: Any) -> list[float]:
    vals: set[float] = set()

    def walk(x, key=None):
        if key in SKIP_KEYS:
            return
        if isinstance(x, bool) or x is None:
            return
        if isinstance(x, (int, float)):
            if math.isfinite(x):
                vals.add(abs(float(x)))
        elif isinstance(x, str):
            vals.update(abs(n["value"]) for n in extract(x))
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v, key)
    walk(digest)
    return sorted(vals)


def _exempt(n: dict) -> bool:
    v = abs(n["value"])
    if n["unit"] or n["decimals"]:
        return False
    return v <= 12 or 1900 <= v <= 2100


def is_grounded(n: dict, allowed: Iterable[float]) -> bool:
    if _exempt(n):
        return True
    v = abs(n["value"])
    tol = 0.5 * 10 ** -n["decimals"] + 1e-9   # half a unit of the last written decimal
    # No bp↔% conversion: it let "40bp" match an unrelated 0.4% move. The digest
    # states spreads in both % and bp instead.
    scales = [1.0]
    if not n["unit"] and n["decimals"] == 0 and v >= 1000:
        scales += [1e-3, 1e-6]                 # 200,000 ↔ 200 (k)
    return any(abs(v * s - a) <= tol * s for s in scales for a in allowed)


def text_fields(obj: Any, path: str = "") -> Iterable[tuple[str, str]]:
    """(path, text) for every string in the LLM output, except ids."""
    if isinstance(obj, str):
        yield path, obj
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in SKIP_KEYS:
                yield from text_fields(v, f"{path}.{k}" if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from text_fields(v, f"{path}[{i}]")


def _nonempty_str(x) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _str_list(x, lo: int, hi: int) -> bool:
    return isinstance(x, list) and lo <= len(x) <= hi and all(_nonempty_str(i) for i in x)


def check_structure(out: Any, news_ids: set[str]) -> list[str]:
    v: list[str] = []
    if not isinstance(out, dict):
        return ["output is not a JSON object"]
    b = out.get("brief")
    if not isinstance(b, dict):
        v.append("missing brief")
    else:
        for k in ("headline", "what_moved", "cycle_view"):
            if not _nonempty_str(b.get(k)):
                v.append(f"brief.{k} missing or empty")
        if not _str_list(b.get("bullets"), 3, 5):
            v.append("brief.bullets must be 3-5 non-empty strings")
    nc = out.get("news_clusters")
    if not isinstance(nc, list) or len(nc) > 6:
        v.append("news_clusters must be a list of at most 6")
    else:
        for i, c in enumerate(nc):
            if not isinstance(c, dict) or not _nonempty_str(c.get("topic")) or not _nonempty_str(c.get("summary")):
                v.append(f"news_clusters[{i}] needs topic and summary")
                continue
            if not isinstance(c.get("tags", []), list):
                v.append(f"news_clusters[{i}].tags must be a list")
            ids = c.get("item_ids")
            if not isinstance(ids, list) or not ids:
                v.append(f"news_clusters[{i}].item_ids must be a non-empty list")
                continue
            bad = [x for x in ids if x not in news_ids]
            if bad:
                v.append(f"news_clusters[{i}].item_ids not in the digest: {', '.join(map(str, bad[:5]))}")
    r = out.get("regime_explainer")
    if not isinstance(r, dict):
        v.append("missing regime_explainer")
    else:
        if not _nonempty_str(r.get("rationale")):
            v.append("regime_explainer.rationale missing or empty")
        for k in ("asset_tendencies", "caveats"):
            if not _str_list(r.get(k), 1, 6):
                v.append(f"regime_explainer.{k} must be 1-6 non-empty strings")
    return v


def validate(out: Any, digest: dict) -> list[str]:
    """All violations (structure + ungrounded numbers). Empty list = accept."""
    news_ids = {n["id"] for n in digest.get("news", [])}
    violations = check_structure(out, news_ids)
    if not isinstance(out, dict):
        return violations
    allowed = allowed_numbers(digest)
    for path, text in text_fields(out):
        if path.endswith(".tags") or ".tags[" in path:
            continue
        for n in extract(text):
            if not is_grounded(n, allowed):
                violations.append(f'{path}: number "{n["raw"]}" is not in the input data')
    return violations
