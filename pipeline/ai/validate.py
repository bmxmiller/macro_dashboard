"""Fact check for LLM text: every number must be a digest fact with the right value, unit,
sign and label.

Facts. ``digest_facts()`` turns the digest (built by context.py) into explicit facts: value,
unit (%, pp, bp, k, m, or "" for levels/scores), role (level / prev / chg / score / headline),
direction of change (for levels: value vs prev) and metric keys (cpi, core_cpi, spx, us10y…).
Names, periods, tags, dates and ids are never sources of numbers. Numbers in news headlines are
facts ONLY inside ``news_clusters[*].summary``.

Claims. ``extract()`` parses numbers with sign, thousands commas, decimals and units, including
uppercase/spaced forms ("250K", "9 %", "10 bp", "1.5pc", "4,512.5K"); digits are never truncated
(atomic groups), labels glued to letters (10Y, 2s10s, 3M, 36th) are ignored, and digits inside
known names (S&P 500, Russell 2000…) are masked. Spelled-out quantities ("two hundred thousand",
"five percent") are a violation: numbers must be digits.

A claim is accepted only if some fact passes ALL of:
* value: equal at the digest's own precision (|claim| == |fact|; "3%" never stands for 3.4).
  Plain integers ≥ 1,000 may also match a fact in k or m ("200,000" ↔ 200k).
* unit: the same unit; a unit-less claim may match any unit, "x" matches unit-less.
* sign: an explicit +/− must equal the sign of a change, or of a level's value; otherwise the
  nearest direction verb within 5 words before the number (rose/fell/widened/narrowed…) must
  equal the change's sign, or the level's direction vs its previous value.
* label: if a metric alias (CPI, core PCE, payrolls, 10-year, S&P 500, gold…) appears earlier in
  the same clause, the fact must belong to the nearest such metric.
* prev: a previous value counts only with words like from/previous/prior/ago nearby.
Exempt: unit-less integers 0–12 (counts) and years 1900–2100.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

# ── Claim extraction ───────────────────────────────────────────────────────

NUMBER = re.compile(
    r"(?<![\w.,:/#])"                                    # not glued to a word, decimal, time or mask
    r"(?P<sign>[+\-−–]?)[ ]?[$£€]?"
    r"(?P<num>(?>\d{1,3}(?:,\d{3})+(?!\d)|\d+)(?>\.\d+)?)"   # atomic: never give digits back
    r"(?P<unit>[ ]?(?:%|pc\b|per[ ]?cent\b|percent\b|percentage[ ]points?\b|pp\b|bps?\b|basis[ ]points?\b"
    r"|thousand\b|million\b|billion\b|trillion\b|mn\b|bn\b|tn\b|[kmbx]\b))?",
    re.IGNORECASE)
_UNIT = {"%": "%", "pc": "%", "percent": "%", "per cent": "%", "percentcent": "%", "pp": "pp",
         "percentage point": "pp", "percentage points": "pp", "bp": "bp", "bps": "bp", "basis point": "bp",
         "basis points": "bp", "k": "k", "thousand": "k", "m": "m", "mn": "m", "million": "m",
         "b": "bn", "bn": "bn", "billion": "bn", "tn": "tn", "trillion": "tn", "x": "x"}
_LABEL_SUFFIX = re.compile(r"(?:y|w|d|q|h|s|th|st|nd|rd|m\d|y\d|s\d)", re.IGNORECASE)
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_MONTH_BEFORE = re.compile(_MONTHS + r"\s*$", re.IGNORECASE)
_MONTH_AFTER = re.compile(r"^\s*" + _MONTHS + r"\b", re.IGNORECASE)
PERIOD_INTS = {1, 3, 6, 9, 12}
STATIC_NAMES = ["S&P 500", "Nasdaq 100", "Russell 2000", "Russell 1000", "FTSE 100", "FTSE 250", "Stoxx 600",
                "Euro Stoxx 50", "Nikkei 225", "DAX 40", "Dow 30", "COVID-19", "G7", "G20", "Treasury 20+"]

_SPELLED = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|"
    r"sixty|seventy|eighty|ninety|hundred|a hundred|half a|a quarter|quarter)\b"
    r"(?:[\s-]+[a-z]+){0,2}?[\s-]+(?:percent|per cent|percentage|points?|basis|bps?|thousand|million|billion|trillion)\b",
    re.IGNORECASE)


@dataclass
class Claim:
    value: float          # signed if an explicit sign was written
    decimals: int
    unit: str             # "", %, pp, bp, k, m, bn, tn, x
    explicit_sign: int    # +1 / −1 / 0
    raw: str
    start: int
    end: int


def mask_names(text: str, names: Iterable[str]) -> str:
    """Replace digits inside known names ("S&P 500") with '#', keeping positions."""
    out = text
    for n in sorted({n for n in names if n and any(c.isdigit() for c in n)}, key=len, reverse=True):
        for m in re.finditer(re.escape(n), out, re.IGNORECASE):
            out = out[:m.start()] + re.sub(r"\d", "#", out[m.start():m.end()]) + out[m.end():]
    return out


def extract(text: str, names: Iterable[str] = ()) -> list[Claim]:
    masked = mask_names(text, list(names) + STATIC_NAMES)
    out = []
    for m in NUMBER.finditer(masked):
        sign, num, unit_raw = m.group("sign"), m.group("num"), m.group("unit") or ""
        start, end = m.start("num"), m.end()
        after, before = masked[end:], masked[:m.start()]
        unit_key = re.sub(r"\s+", " ", unit_raw.strip().lower())
        unit = _UNIT.get(unit_key, "")
        is_int = "." not in num
        n = float(num.replace(",", ""))
        if not unit_raw:
            if after[:1].isalpha() and _LABEL_SUFFIX.match(after):     # 10Y, 2s10s, 36th, 3m10y
                continue
            if after[:1] == "-" and after[1:2].isalnum():               # 30-year, 7-10Y
                continue
            if after[:1] == ":" and after[1:2].isdigit():               # 8:30 (time)
                continue
        if unit == "m" and is_int and n in PERIOD_INTS and not unit_raw.startswith(" ") \
                and not after[:1].isalnum():                            # 1M / 3m / 6M periods
            continue
        if sign in ("-", "–") and before[-1:].isalnum():                # 2026-11-13, 7-10
            continue
        if not sign and before[-1:] in ("-", "–") and before[-2:-1].isalnum():
            continue
        if is_int and n <= 31 and not unit and (_MONTH_BEFORE.search(before) or _MONTH_AFTER.match(after)):
            continue                                                    # "Nov 13", "13 Nov"
        if is_int and "," not in num and 1900 <= n <= 2100 and not unit:
            continue                                                    # years
        explicit = -1 if sign in ("-", "−", "–") else (1 if sign == "+" else 0)
        out.append(Claim(value=-n if explicit < 0 else n, decimals=0 if is_int else len(num.split(".")[1]),
                         unit=unit, explicit_sign=explicit, raw=m.group(0).strip(), start=start, end=end))
    return out


def spelled_numbers(text: str) -> list[str]:
    return [m.group(0) for m in _SPELLED.finditer(text)]


# ── Metric aliases (label awareness) ───────────────────────────────────────

ALIASES = {
    "core cpi": "core_cpi", "core consumer prices": "core_cpi", "core pce": "core_pce", "pce": "core_pce",
    "core inflation": "core", "core": "core",
    "uk core cpi": "uk_core_cpi", "uk cpi": "uk_cpi", "uk inflation": "uk_cpi",
    "cpi": "cpi", "headline inflation": "cpi", "consumer prices": "cpi", "consumer price inflation": "cpi",
    "ppi": "ppi", "producer prices": "ppi", "inflation": "inflation", "breakeven": "breakeven",
    "uk unemployment": "uk_unemployment", "unemployment": "unemployment", "jobless rate": "unemployment",
    "payrolls": "nfp", "nonfarm": "nfp", "non-farm": "nfp", "nfp": "nfp", "jobs": "nfp", "job gains": "nfp",
    "jobless claims": "claims", "initial claims": "claims", "claims": "claims",
    "real policy rate": "real_rate", "real rate": "real_rate",
    "fed funds": "fed_funds", "federal funds": "fed_funds", "policy rate": "fed_funds",
    "10-year gilt": "gilt", "10y gilt": "gilt", "2-year gilt": "gilt", "2y gilt": "gilt", "gilt": "gilt", "gilts": "gilt",
    "10-year": "us10y", "10y": "us10y", "10 year": "us10y", "ten-year": "us10y",
    "2-year": "us2y", "2y": "us2y", "two-year": "us2y",
    "2s10s": "2s10s", "3m10y": "3m10y", "vix": "vix",
    "s&p 500": "spx", "s&p": "spx", "spx": "spx", "nasdaq": "nasdaq", "dow": "dow", "russell": "russell",
    "gold": "gold", "oil": "oil", "wti": "oil", "brent": "oil", "crude": "oil",
    "high-yield spread": "hy", "high yield spread": "hy", "hy spread": "hy", "credit spread": "hy",
    "hy oas": "hy", "junk bond spread": "hy",
    "uk gdp": "uk_gdp", "gdp": "gdp", "bank rate": "bank_rate",
    "fear & greed": "fear_greed", "fear and greed": "fear_greed",
}
GROUPS = {  # alias key → fact keys it may refer to
    "inflation": {"cpi", "core_cpi", "core_pce", "ppi", "uk_cpi", "uk_core_cpi", "breakeven", "inflation"},
    "core": {"core_cpi", "core_pce", "uk_core_cpi"},
    "unemployment": {"unemployment", "uk_unemployment"},
    "gdp": {"gdp", "uk_gdp"},
}
METRIC_KEYS = {
    "cpi_yoy": "cpi", "core_cpi_yoy": "core_cpi", "core_pce_yoy": "core_pce", "ppi_yoy": "ppi",
    "breakeven_5y": "breakeven", "nfp": "nfp", "unrate": "unemployment", "claims": "claims", "gdp_qoq": "gdp",
    "fed_funds": "fed_funds", "hy_oas": "hy", "vix": "vix", "indpro_yoy": "indpro", "sahm": "sahm",
    "uk_cpi_yoy": "uk_cpi", "uk_core_cpi_yoy": "uk_core_cpi", "uk_unemployment": "uk_unemployment",
    "uk_gdp_qoq": "uk_gdp", "uk_gdp_yoy": "uk_gdp", "uk_bank_rate": "bank_rate",
    "uk_gilt_2y": "gilt", "uk_gilt_10y": "gilt",
}
_ALIAS_RE = re.compile(
    r"(?<![a-z0-9&])(" + "|".join(re.escape(a) for a in sorted(ALIASES, key=len, reverse=True)) + r")(?![a-z0-9])",
    re.IGNORECASE)
_CLAUSE_BREAK = re.compile(
    r"[;!?]|\.(?=\s|$)|,\s|\s[—–-]\s|\(|\)|\b(?:vs\.?|versus|compared (?:with|to)|than|while|whereas|but|above|below)\b",
    re.IGNORECASE)


def alias_keys(text: str) -> set[str]:
    return {ALIASES[m.group(1).lower()] for m in _ALIAS_RE.finditer(text)}


def nearest_alias(text: str, pos: int) -> str | None:
    """Alias key closest before `pos` within the same clause."""
    starts = [m.end() for m in _CLAUSE_BREAK.finditer(text, 0, pos)]
    clause_start = max(starts) if starts else 0
    found = None
    for m in _ALIAS_RE.finditer(text, clause_start, pos):
        found = ALIASES[m.group(1).lower()]
    return found


# ── Direction words ────────────────────────────────────────────────────────

UP_WORDS = {"rose", "rise", "rises", "rising", "up", "gained", "gain", "gains", "gaining", "increased", "increase",
            "increases", "climbed", "climb", "climbs", "jumped", "jump", "jumps", "advanced", "rallied", "rally",
            "widened", "widen", "widens", "grew", "grow", "grows", "higher", "accelerated", "surged", "surge",
            "added", "firmed", "steepened", "rebounded", "picked"}
DOWN_WORDS = {"fell", "fall", "falls", "falling", "down", "declined", "decline", "declines", "dropped", "drop",
              "drops", "decreased", "decrease", "slipped", "slip", "slid", "lost", "lose", "contracted", "contract",
              "narrowed", "narrow", "narrows", "eased", "ease", "eases", "lower", "tumbled", "sank", "retreated",
              "cooled", "slowed", "shed", "flattened", "dipped", "dip", "plunged", "slumped"}
PREV_BEFORE = {"from", "previous", "previously", "prior", "earlier", "last"}
PREV_AFTER = {"ago", "earlier", "before", "previously", "prior"}
_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")


def verb_sign(text: str, pos: int, window: int = 5) -> int:
    words = _WORD.findall(text[max(0, pos - 80):pos])[-window:]
    for w in reversed(words):
        w = w.lower()
        if w in UP_WORDS:
            return 1
        if w in DOWN_WORDS:
            return -1
    return 0


def prev_context(text: str, start: int, end: int) -> bool:
    before = {w.lower() for w in _WORD.findall(text[max(0, start - 60):start])[-4:]}
    after = {w.lower() for w in _WORD.findall(text[end:end + 40])[:3]}
    return bool(before & PREV_BEFORE or after & PREV_AFTER)


# ── Facts from the digest ──────────────────────────────────────────────────

@dataclass
class Fact:
    value: float
    unit: str
    role: str                     # level | prev | chg | score | headline
    direction: int | None = None  # +1 / −1 / 0 for levels (vs prev); None if unknown
    keys: frozenset = field(default_factory=frozenset)


_UNIT_FIELD = {"%": "%", "k": "k", "m": "m", "pp": "pp", "bp": "bp", "idx": "", "": ""}
_SUFFIX_UNIT = (("_pct", "%"), ("_pp", "pp"), ("_bp", "bp"), ("_k", "k"))


def _sgn(x: float | None) -> int | None:
    if x is None:
        return None
    return (x > 0) - (x < 0)


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _suffix_unit(key: str) -> str:
    return next((u for s, u in _SUFFIX_UNIT if key.endswith(s)), "")


def digest_facts(d: dict) -> tuple[list[Fact], list[Fact], list[str]]:
    """(facts, headline facts, names to mask) from a context.py digest."""
    facts: list[Fact] = []
    names: list[str] = []
    add = facts.append
    mk = d.get("markets", {})
    for r in mk.get("index_snapshot", []):
        names.append(r.get("name", ""))
        keys = frozenset(alias_keys(f"{r.get('name', '')} {r.get('tag', '')}"))
        chg = next((r[k] for k in r if k.startswith(("ret_", "chg_")) and _num(r[k])), None)
        for k, v in r.items():
            if not _num(v):
                continue
            if k.startswith(("ret_", "chg_")):
                add(Fact(v, _suffix_unit(k), "chg", keys=keys))
            elif k.startswith("level"):
                add(Fact(v, _suffix_unit(k), "level", _sgn(chg), keys))
    for title, panel in mk.items():
        if title == "index_snapshot":
            continue
        for per in panel.values():
            for side in per.values():
                for r in side:
                    names.append(r.get("name", ""))
                    keys = frozenset(alias_keys(f"{r.get('name', '')} {r.get('tag', '')}"))
                    for k, v in r.items():
                        if _num(v) and k.startswith(("ret_", "chg_")):
                            add(Fact(v, _suffix_unit(k), "chg", keys=keys))
    for section in ("economy", "uk"):
        for mid, m in (d.get(section) or {}).items():
            names.append(m.get("name", ""))
            key = METRIC_KEYS.get(mid, mid)
            keys = frozenset({key})
            unit = _UNIT_FIELD.get(m.get("units") or "", m.get("units") or "")
            v, p = m.get("value"), m.get("prev")
            direction = _sgn(v - p) if _num(v) and _num(p) else None
            if _num(v):
                add(Fact(v, unit, "level", direction, keys))
            if _num(p):
                add(Fact(p, unit, "prev", direction, keys))
            if _num(m.get("z")):
                add(Fact(m["z"], "", "score", keys=keys))
    yc = d.get("yield_curve") or {}
    for label, v in (yc.get("tenors_pct") or {}).items():
        key = {"10Y": "us10y", "2Y": "us2y"}.get(label, f"ust_{label}")
        if _num(v):
            add(Fact(v, "%", "level", None, frozenset({key, "treasury"})))
    for s in yc.get("spreads", []):
        keys = frozenset({s.get("label", "").lower()})
        direction = _sgn(s.get("chg_1m_bp"))
        for k, v in s.items():
            if not _num(v):
                continue
            add(Fact(v, _suffix_unit(k), "chg" if k.startswith("chg") else "level", direction, keys))
    sent = d.get("sentiment") or {}
    if (fg := sent.get("fear_greed")):
        keys = frozenset({"fear_greed"})
        for k, v in fg.items():
            if _num(v):
                add(Fact(v, "", "prev" if "ago" in k else "level", None, keys))
    if (vt := sent.get("vix_term")):
        for k, v in vt.items():
            if _num(v):
                add(Fact(v, "", "level", None, frozenset({"vix"} if k in ("vix", "vix3m", "ratio") else {"vix_term"})))
    for p in d.get("positioning_extremes", []):
        names.append(p.get("name", ""))
        keys = frozenset(alias_keys(p.get("name", "")) | {"positioning"})
        if _num(p.get("pctile_3y")):
            add(Fact(p["pctile_3y"], "", "level", None, keys))
        if _num(p.get("net_pct_oi")):
            add(Fact(p["net_pct_oi"], "%", "level", None, keys))
    if (rg := d.get("regime")):
        _regime_facts(rg, add)
    headline = [Fact(c.value, c.unit, "headline", None, frozenset())
                for n in d.get("news", []) for c in extract(n.get("title", ""))]
    return facts, headline, names


def _regime_facts(rg: dict, add) -> None:
    gi = rg.get("growth_inflation") or {}
    for side, key in (("growth", "growth"), ("inflation", "inflation")):
        s = gi.get(side) or {}
        if _num(s.get("score")):
            add(Fact(s["score"], "", "score", keys=frozenset({key})))
        for c in s.get("components", []):
            keys = frozenset({c.get("metric", ""), key})
            for k, v in c.items():
                if not _num(v):
                    continue
                if k == "score" or k.startswith("value"):
                    add(Fact(v, _suffix_unit(k), "chg", keys=keys))
                else:
                    add(Fact(v, _suffix_unit(k), "prev" if "ago" in k else "level", None, keys))
    if _num(gi.get("core_pce_pct")):
        add(Fact(gi["core_pce_pct"], "%", "level", None, frozenset({"core_pce", "inflation"})))
    if _num(gi.get("inflation_target_pct")):
        add(Fact(gi["inflation_target_pct"], "%", "level", None, frozenset({"inflation", "target"})))
    gp = rg.get("growth_policy") or {}
    gp_keys = {"fed_funds_upper_pct": {"fed_funds"}, "fed_funds_mid_pct": {"fed_funds"},
               "core_pce_pct": {"core_pce", "inflation"}, "real_rate_pct": {"real_rate"}}
    for k, v in gp.items():
        if _num(v):
            add(Fact(v, _suffix_unit(k), "level", None, frozenset(gp_keys.get(k, {"real_rate"}))))
        elif k == "neutral_band_pct" and isinstance(v, list):
            for x in v:
                if _num(x):
                    add(Fact(x, "%", "level", None, frozenset({"real_rate", "neutral"})))
    cd = rg.get("credit_duration") or {}
    if _num(cd.get("score_pp")):
        add(Fact(cd["score_pp"], "pp", "chg", keys=frozenset({"credit"})))
    if _num(cd.get("hy_oas_3m_chg_bp")):
        add(Fact(cd["hy_oas_3m_chg_bp"], "bp", "chg", keys=frozenset({"hy"})))
    for p in cd.get("pairs", []):
        for k, v in p.items():
            if _num(v):
                add(Fact(v, _suffix_unit(k), "chg", keys=frozenset({"credit", str(p.get("long", "")).lower(),
                                                                    str(p.get("short", "")).lower()})))


# ── Matching ───────────────────────────────────────────────────────────────

def _exempt(c: Claim) -> bool:
    return not c.unit and c.decimals == 0 and abs(c.value) <= 12


def _value_unit_ok(c: Claim, f: Fact) -> bool:
    v = abs(c.value)
    if c.unit in ("", "x") and (f.unit == "" or c.unit == ""):
        if abs(v - abs(f.value)) < 1e-6:
            return True
    elif c.unit == f.unit and abs(v - abs(f.value)) < 1e-6:
        return True
    if not c.unit and c.decimals == 0 and v >= 1000:     # 200,000 ↔ 200k ; 1,221,000 ↔ 1.221m
        return (f.unit == "k" and abs(v / 1e3 - abs(f.value)) < 1e-6) or \
               (f.unit == "m" and abs(v / 1e6 - abs(f.value)) < 1e-6)
    return False


def _sign_ok(c: Claim, f: Fact, verb: int) -> bool:
    if f.role == "headline":
        return True
    if c.explicit_sign:
        return _sgn(f.value) in (c.explicit_sign, 0) if f.role in ("chg", "score") else \
            (_sgn(f.value) == c.explicit_sign or (c.explicit_sign > 0 and f.value >= 0))
    if not verb:
        return True
    expected = _sgn(f.value) if f.role in ("chg", "score") else f.direction
    return expected is None or expected == verb


def check_claim(c: Claim, text: str, facts: list[Fact], headline: list[Fact], in_summary: bool) -> str | None:
    """None if grounded, else the reason."""
    if _exempt(c):
        return None
    pool = facts + (headline if in_summary else [])
    cands = [f for f in pool if _value_unit_ok(c, f)]
    if not cands:
        same_unit = [f for f in pool if f.unit == c.unit or not c.unit]
        if any(abs(round(abs(f.value), c.decimals) - abs(c.value)) < 1e-6 for f in same_unit):
            return "is rounded more coarsely than the data: copy the exact value"
        if any(abs(abs(c.value) - abs(f.value)) < 1e-6 for f in pool):
            return "unit does not match the data"
        if not in_summary and any(_value_unit_ok(c, f) for f in headline):
            return "headline numbers may only be quoted in news_clusters summaries"
        return "not in the input data at that precision"
    alias = nearest_alias(text, c.start)
    if alias:
        want = GROUPS.get(alias, {alias})
        labelled = [f for f in cands if f.keys & want or (in_summary and f.role == "headline")]
        if not labelled:
            return f'not the value of "{alias.replace("_", " ")}" (check the metric name before it)'
        cands = labelled
    if not prev_context(text, c.start, c.end):
        current = [f for f in cands if f.role != "prev"]
        if not current:
            return 'is a previous value: say "from …" / "previous", or use the latest value'
        cands = current
    verb = verb_sign(text, c.start)
    if not any(_sign_ok(c, f, verb) for f in cands):
        return "direction (sign or rose/fell) contradicts the data"
    return None


# ── Structure ──────────────────────────────────────────────────────────────

SKIP_KEYS = {"id", "item_ids", "tags", "asof", "date", "published", "url", "period", "name", "label", "tag",
             "units", "source"}


def text_fields(obj: Any, path: str = "") -> Iterable[tuple[str, str]]:
    """(path, text) for every string in the LLM output, except ids and tags."""
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
        if not _str_list(r.get("caveats"), 1, 4):
            v.append("regime_explainer.caveats must be 1-4 non-empty strings")
    return v


_SUMMARY_PATH = re.compile(r"^news_clusters\[\d+\]\.summary$")


def check_numbers(out: dict, digest: dict) -> list[str]:
    facts, headline, names = digest_facts(digest)
    v = []
    for path, text in text_fields(out):
        for s in spelled_numbers(text):
            v.append(f'{path}: "{s}": write numbers as digits copied from the data')
        in_summary = bool(_SUMMARY_PATH.match(path))
        for c in extract(text, names):
            reason = check_claim(c, text, facts, headline, in_summary)
            if reason:
                v.append(f'{path}: "{c.raw}" {reason}')
    return v


def validate(out: Any, digest: dict) -> list[str]:
    """All violations (structure + numbers + semantics). Empty list = accept."""
    news_ids = {n["id"] for n in digest.get("news", [])}
    violations = check_structure(out, news_ids)
    if not isinstance(out, dict):
        return violations
    return violations + check_numbers(out, digest)
