"""Pipeline entry point: fetch → transform → validate → write JSON for the web app.

    python -m pipeline.build                 # everything
    python -m pipeline.build --only markets  # one section

Each section is isolated: if a source fails, the previous good JSON is kept and
the failure is recorded in meta.json so the UI can flag that panel as stale.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from .ai.insights import build_insights
from .ai.regime_section import build_regime
from .ai.llm import NoProviderAvailable
from .fetchers import boe, cftc, cnn, earnings, fomc, fred, news, ons, sp500, yahoo
from .fetchers.http import RedactingFilter, redact
from .schemas import UK, SP500, Calendar, Earnings, Economy, Markets, News, Positioning, Sentiment, SP500History, YieldCurve
from .transforms import econ
from .transforms import sp500 as sp500_tx
from .transforms.returns import PERIODS, period_returns, sparkline, trailing_yield

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = Path(__file__).resolve().parent / "registry"
OUT = ROOT / "web" / "public" / "data"

log = logging.getLogger("build")


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Minimal .env loader for local runs (CI uses GitHub Secrets as env vars)."""
    import os
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_yaml(name: str) -> dict:
    return yaml.safe_load((REGISTRY / name).read_text(encoding="utf-8"))


def write_json(name: str, model) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(mode="json") if hasattr(model, "model_dump") else model
    (OUT / name).write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    log.info("wrote %s (%.1f KB)", name, (OUT / name).stat().st_size / 1024)


def clean(v):
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


# ── Markets ────────────────────────────────────────────────────────────────

def build_markets() -> Markets:
    uni = load_yaml("universes.yaml")["panels"]
    tickers = [it["t"] for p in uni.values() for g in p["groups"] for it in g["items"]]
    px = yahoo.fetch_prices(tickers, period="4y")

    panels = {}
    missing = []
    for pid, p in uni.items():
        groups = []
        for g in p["groups"]:
            rows = []
            for it in g["items"]:
                t = it["t"]
                tr = px.adj_close[t].dropna() if t in px.adj_close else pd.Series(dtype=float)
                cl = px.close[t].dropna() if t in px.close else pd.Series(dtype=float)
                if tr.empty:
                    missing.append(t)
                    continue
                mode = "diff" if it.get("kind") == "yield" or t == "^TNX" else "pct"
                series = 1 / tr if it.get("invert") else tr
                rows.append({
                    "ticker": t,
                    "name": it["name"],
                    "tag": it.get("tag", t),
                    # Inverted FX: returns are foreign-ccy vs USD, but the price stays the
                    # market-convention quote (USD/JPY), so label it explicitly.
                    "units": f"{it.get('tag', t)} per USD" if it.get("invert") else it.get("units"),
                    "price": round(float(cl.iloc[-1]), 4) if not cl.empty else None,
                    "asof": cl.index[-1].strftime("%Y-%m-%d") if not cl.empty else None,
                    "mode": mode,
                    "returns": period_returns(series, mode=mode),
                    "spark": sparkline(series),
                    "yield_ttm": trailing_yield(cl, px.dividends[t]) if "dur" in it else None,
                    "duration": it.get("dur"),
                    "source_url": yahoo.quote_url(t),
                })
            groups.append({"label": g["label"], "rows": rows})
        panels[pid] = {"id": pid, "title": p["title"], "about": p["about"], "groups": groups}
    if missing:
        log.warning("no price data for: %s", ", ".join(missing))
    if len(missing) > 0.25 * len(set(tickers)):
        # Fail the section so the last good markets.json is kept and flagged stale,
        # instead of publishing a mostly-empty file marked ok.
        raise RuntimeError(f"price data missing for {len(missing)} of {len(set(tickers))} tickers")
    return Markets(generated_at=now_iso(), periods=PERIODS, panels=panels)


# ── Economy ────────────────────────────────────────────────────────────────

def _series_ids(metrics: list[dict]) -> list[str]:
    ids = []
    for m in metrics:
        ids += [m["numerator"], m["denominator"]] if m["transform"] == "ratio" else [m["series"]]
    return ids


def recession_periods(usrec: pd.Series) -> list[list[str]]:
    periods, start = [], None
    for d, v in usrec.items():
        if v >= 1 and start is None:
            start = d
        elif v < 1 and start is not None:
            periods.append([start.strftime("%Y-%m-%d"), d.strftime("%Y-%m-%d")])
            start = None
    if start is not None:
        periods.append([start.strftime("%Y-%m-%d"), usrec.index[-1].strftime("%Y-%m-%d")])
    return periods


def build_economy() -> Economy:
    reg = load_yaml("metrics.yaml")
    metrics = reg["metrics"]
    raw = fred.fetch_many(_series_ids(metrics) + ["USREC"], start="1995-01-01")

    out = []
    for m in metrics:
        try:
            needed = [m["numerator"], m["denominator"]] if m["transform"] == "ratio" else [m["series"]]
            for sid in needed:
                if isinstance(raw.get(sid), Exception):
                    raise raw[sid]
            s = econ.apply_transform(m, raw)
            if s.empty:
                raise ValueError("empty series")
        except Exception as e:  # noqa: BLE001
            log.warning("metric %s failed: %s", m["id"], e)
            continue
        primary = m.get("series") or m["numerator"]
        row = _metric_row(m, s, fred.series_url(primary))
        try:
            row["alt"] = _alt_view(m, raw)
        except Exception as e:  # noqa: BLE001 - the toggle is optional; never lose the metric over it
            log.warning("metric %s alt view failed: %s", m["id"], e)
        out.append(row)

    usrec = raw.get("USREC")
    recs = recession_periods(usrec) if isinstance(usrec, pd.Series) else []
    if not out:
        raise RuntimeError("no economic metrics could be built")
    return Economy(generated_at=now_iso(), groups=reg["groups"], metrics=out, recessions=recs)


# ── Yield curve ────────────────────────────────────────────────────────────

def build_yield_curve() -> YieldCurve:
    yc = load_yaml("metrics.yaml")["yield_curve"]
    ids = [t["series"] for t in yc["tenors"]] + [s["series"] for s in yc["spreads"]]
    raw = fred.fetch_many(ids, start=str(date.today().year - 6) + "-01-01")

    asof = None
    points = []
    for t in yc["tenors"]:
        s = raw.get(t["series"])
        if not isinstance(s, pd.Series) or s.empty:
            points.append({"label": t["label"], "years": t["years"], "now": None, "m1": None, "y1": None})
            continue
        last = s.index[-1]
        asof = max(asof, last) if asof is not None else last
        def at(off):  # noqa: E306
            sub = s.loc[:last - off]
            return round(float(sub.iloc[-1]), 3) if not sub.empty else None
        points.append({
            "label": t["label"], "years": t["years"],
            "now": round(float(s.iloc[-1]), 3),
            "m1": at(pd.DateOffset(months=1)), "y1": at(pd.DateOffset(years=1)),
        })

    spreads = []
    for sp in yc["spreads"]:
        s = raw.get(sp["series"])
        if not isinstance(s, pd.Series) or s.empty:
            continue
        spreads.append({
            "label": sp["label"], "series": sp["series"],
            "value": round(float(s.iloc[-1]), 3),
            "m1": clean(s.loc[:s.index[-1] - pd.DateOffset(months=1)].iloc[-1]),
            "history": econ.history(s, years=6),
            "data_url": fred.series_url(sp["series"]),
        })
    got = sum(p["now"] is not None for p in points)
    if got < len(points) // 2:
        raise RuntimeError(f"only {got}/{len(points)} Treasury tenors fetched; keeping previous curve")
    return YieldCurve(
        generated_at=now_iso(), asof=asof.strftime("%Y-%m-%d") if asof is not None else None,
        about={k: yc["about"][k] for k in ("what", "why", "how_to_read")},
        source_url=yc["source_url"], points=points, spreads=spreads,
    )


# ── Calendar ───────────────────────────────────────────────────────────────

RELEASE_META = {  # metric id → (display name, ET release time, importance)
    "cpi_yoy": ("Consumer Prices (CPI)", "8:30 AM ET", "high"),
    "ppi_yoy": ("Producer Prices (PPI)", "8:30 AM ET", "medium"),
    "core_pce_yoy": ("PCE Inflation / Personal Income", "8:30 AM ET", "high"),
    "nfp": ("Jobs Report (NFP)", "8:30 AM ET", "high"),
    "claims": ("Initial Jobless Claims", "8:30 AM ET", "low"),
    "jolts": ("JOLTS Job Openings", "10:00 AM ET", "medium"),
    "gdp_qoq": ("GDP Report", "8:30 AM ET", "high"),
    "retail_mom": ("Retail Sales", "8:30 AM ET", "medium"),
    "umich": ("UMich Consumer Sentiment", "10:00 AM ET", "medium"),
    "indpro_yoy": ("Industrial Production", "9:15 AM ET", "low"),
    "housing_starts": ("Housing Starts", "8:30 AM ET", "low"),
}


def _minutes(t: str | None) -> int:
    """'8:30 AM ET' → 510. Sorting the raw strings would put 10:00 before 8:30."""
    if not t:
        return 24 * 60
    try:
        hm, ampm = t.split()[:2]
        h, m = (int(x) for x in hm.split(":"))
        return (h % 12 + (12 if ampm.upper() == "PM" else 0)) * 60 + m
    except ValueError:
        return 24 * 60


def _fmt(m: dict) -> str:
    v = m["value"]
    sign = "+" if m["units"] in ("%", "k") and v > 0 and m["id"] in ("nfp", "retail_mom", "gdp_qoq") else ""
    return f"{sign}{v:,.{m['decimals']}f}{m['units'] if m['units'] in ('%', 'k', 'm') else ''}"


def build_calendar(economy: Economy | None) -> Calendar:
    today = date.today().isoformat()
    metrics = {m.id: m.model_dump() for m in economy.metrics} if economy else {}
    events = []

    fed = metrics.get("fed_funds")
    for mt in fomc.fetch_meetings():
        if mt["date"] < today:
            continue
        events.append({
            "date": mt["date"], "time": "2:00 PM ET",
            "name": "Fed Decision (FOMC)" + (" + Projections" if mt["sep"] else ""),
            "kind": "fomc", "metric_id": "fed_funds", "importance": "high",
            "last_value": f"{fed['value'] - 0.25:.2f}–{fed['value']:.2f}%" if fed else None,
            "last_label": "RANGE", "source_url": fomc.URL,
        })

    complete = False
    note = None
    if fred.api_key():
        reg = {m["id"]: m for m in load_yaml("metrics.yaml")["metrics"]}
        rel_to_metric = {}
        for mid in RELEASE_META:
            m = reg.get(mid)
            if not m:
                continue
            try:
                rel = fred.release_for_series(m.get("series") or m["numerator"])
                if rel:
                    rel_to_metric[rel["id"]] = mid
            except Exception as e:  # noqa: BLE001
                log.warning("release lookup %s failed: %s", mid, e)
        seen = set()
        try:
            release_dates = fred.upcoming_release_dates(days_ahead=45)
            complete = True
        except Exception as e:  # noqa: BLE001 - degrade to FOMC-only rather than fail
            log.warning("FRED release calendar failed: %s", redact(str(e)))
            release_dates, note = [], "Release dates temporarily unavailable; showing FOMC only."
        for rd in release_dates:
            mid = rel_to_metric.get(rd["release_id"])
            if not mid or rd["date"] < today or (mid, rd["date"]) in seen:
                continue
            seen.add((mid, rd["date"]))
            name, time, imp = RELEASE_META[mid]
            m = metrics.get(mid)
            events.append({
                "date": rd["date"], "time": time, "name": name, "kind": "release",
                "metric_id": mid, "importance": imp,
                "last_value": _fmt(m) if m else None,
                "last_label": m["name"].upper() if m else None,
                "source_url": reg[mid]["source_url"],
            })
    else:
        note = "Set FRED_API_KEY to include data-release dates (CPI, jobs, GDP…). Showing FOMC only."

    events.sort(key=lambda e: (e["date"], _minutes(e["time"])))
    return Calendar(generated_at=now_iso(), complete=complete, note=note, events=events)


# ── UK ─────────────────────────────────────────────────────────────────────

def _metric_row(m: dict, s: pd.Series, data_url: str, period_label: str | None = None) -> dict:
    """One indicator row (shared by the economy and UK sections).

    `step: true` in the registry marks policy-rate series: prev is then the last
    value different from the current one (see econ.prev_and_change).
    """
    last_d = s.index[-1]
    ya = s.loc[:last_d - pd.DateOffset(years=1)]
    prev, change = econ.prev_and_change(s, step=bool(m.get("step")))
    return {
        "id": m["id"], "group": m["group"], "name": m["name"], "units": m["units"],
        "decimals": m["decimals"], "good": m["good"], "frequency": m["frequency"],
        "value": round(float(s.iloc[-1]), 4),
        "date": last_d.strftime("%Y-%m-%d"),
        "period_label": period_label or econ.period_label(last_d, m["frequency"]),
        "prev": prev,
        "change": change,
        "year_ago": round(float(ya.iloc[-1]), 4) if not ya.empty else None,
        "zscore": econ.zscore(s),
        "percentile": econ.percentile(s),
        "history": econ.history(s),
        "about": m["about"],
        "source_url": m["source_url"],
        "data_url": data_url,
    }


_VIEW_LABEL = {"yoy": "YoY", "mom_pct": "MoM"}


def _alt_view(m: dict, raw: dict) -> dict | None:
    """Second transform of the same raw series (registry `alt_transform`) for the YoY/MoM toggle."""
    alt_t = m.get("alt_transform")
    if not alt_t:
        return None
    s = econ.apply_transform({**m, "transform": alt_t}, raw)
    if s.empty:
        return None
    decimals = 2 if alt_t == "mom_pct" else 1  # monthly changes are small: 0.31%, not 0.3%
    prev, change = econ.prev_and_change(s)
    label, primary = _VIEW_LABEL[alt_t], _VIEW_LABEL[m["transform"]]
    name = m["name"].replace(primary, label) if primary in m["name"] else f"{m['name']} {label}"
    return {
        "label": label, "primary_label": primary, "name": name, "decimals": decimals,
        "value": round(float(s.iloc[-1]), 4), "prev": prev, "change": change,
        "zscore": econ.zscore(s), "percentile": econ.percentile(s), "history": econ.history(s),
    }


def _previous_history(section: str, metric_id: str) -> pd.Series:
    """History of one metric from the last good JSON (used to extend short-window sources)."""
    try:
        data = json.loads((OUT / f"{section}.json").read_text(encoding="utf-8"))
        hist = next(m["history"] for m in data["metrics"] if m["id"] == metric_id)
        return pd.Series({pd.Timestamp(d): float(v) for d, v in hist}, dtype=float).sort_index()
    except Exception:  # noqa: BLE001 - no previous file / metric yet
        return pd.Series(dtype=float)


def _uk_gilt_glc(m: dict) -> pd.Series:
    """2y gilt from BoE GLC files: current month + stored history, bootstrapping from the archive once."""
    prev = _previous_history("uk", m["id"])
    need_bootstrap = prev.empty or prev.index[0] > pd.Timestamp.today() - pd.DateOffset(years=5)
    if need_bootstrap:
        log.info("uk: bootstrapping %s history from the BoE GLC archive", m["id"])
    s = boe.fetch_glc_spot(float(m["tenor"]), bootstrap=need_bootstrap)
    if not prev.empty:
        s = pd.concat([prev.loc[:s.index[0] - pd.Timedelta(days=1)], s])
    return s[~s.index.duplicated(keep="last")].sort_index()


def build_uk() -> UK:
    reg = load_yaml("uk.yaml")
    metrics = reg["metrics"]
    codes = sorted({m["series"] for m in metrics if m["source"] == "boe"}
                   | {m["fallback_boe"] for m in metrics if m.get("fallback_boe")})
    try:
        iadb = boe.fetch_iadb(codes, start="2000-01-01")
    except Exception as e:  # noqa: BLE001 - surfaced per metric below
        log.warning("uk: BoE IADB failed: %s", e)
        iadb = e

    def from_iadb(code: str) -> pd.Series:
        if isinstance(iadb, Exception):
            raise iadb
        if code not in iadb or iadb[code].empty:
            raise ValueError(f"IADB returned no data for {code}")
        return iadb[code]

    out = []
    for m in metrics:
        try:
            src = m["source"]
            label = None
            if src == "ons":
                raw = ons.fetch_series(m["uri"], m["frequency"], m.get("alt_uris"))
                url = ons.series_url(m["uri"])
                window = m.get("window_months") or raw.attrs.get("window_months")
                if window:  # rolling 3-month average: label the whole window
                    label = ons.window_label(raw.index[-1], int(window))
            elif src == "boe":
                raw, url = from_iadb(m["series"]), boe.series_url(m["series"])
            elif src == "boe_glc":
                raw, url = _uk_gilt_glc(m), boe.YIELD_CURVE_PAGE
            elif src == "yahoo":
                try:
                    px = yahoo.fetch_prices([m["series"]], period="10y").close[m["series"]].dropna()
                    if px.empty:
                        raise ValueError("empty price series")
                    raw, url = px, yahoo.quote_url(m["series"])
                except Exception as e:  # noqa: BLE001
                    if not m.get("fallback_boe"):
                        raise
                    log.warning("uk: yahoo %s failed (%s); using BoE %s", m["series"], e, m["fallback_boe"])
                    raw, url = from_iadb(m["fallback_boe"]), boe.series_url(m["fallback_boe"])
            else:
                raise ValueError(f"unknown source {src}")
            s = econ.apply_transform({**m, "series": m["id"]}, {m["id"]: raw})
            if s.empty:
                raise ValueError("empty series")
            if label and s.index[-1] != raw.index[-1]:
                label = None  # transform shifted the last date; fall back to the plain label
            out.append(_metric_row(m, s, url, label))
        except Exception as e:  # noqa: BLE001
            log.warning("uk metric %s failed: %s", m["id"], e)
    if not out:
        raise RuntimeError("no UK metrics could be built")
    return UK(generated_at=now_iso(), groups=reg["groups"], metrics=out)


# ── Positioning (CFTC Commitments of Traders) ──────────────────────────────

def build_positioning() -> Positioning:
    reg = load_yaml("positioning.yaml")
    since = (pd.Timestamp.today() - pd.DateOffset(years=3, weeks=3)).strftime("%Y-%m-%d")
    markets = []
    for mk in reg["markets"]:
        try:
            rows = cftc.fetch_rows(mk["code"], mk["report"], since)
            df = cftc.parse_rows(rows, mk["report"])
            cfg = cftc.REPORTS[mk["report"]]
            markets.append({
                "id": mk["id"], "name": mk["name"], "asset_class": mk["asset_class"],
                "report": mk["report"], "report_name": cfg["report"], "trader_group": cfg["group"],
                "contract_code": mk["code"],
                "exchange_name": rows[-1].get("market_and_exchange_names"),
                **cftc.summarize(df),
                "about": mk["about"],
                "source_url": cftc.COT_PAGE,
                "data_url": cftc.dataset_url(mk["report"]),
            })
        except Exception as e:  # noqa: BLE001
            log.warning("positioning %s failed: %s", mk["id"], e)
        time.sleep(0.3)  # be polite to the Socrata API
    if not markets:
        raise RuntimeError("no COT markets could be built")
    return Positioning(
        generated_at=now_iso(), report_date=max(m["report_date"] for m in markets),
        about=reg["about"], source_url=cftc.COT_PAGE, markets=markets,
    )


# ── Sentiment ──────────────────────────────────────────────────────────────

def vix_term_structure(close: pd.DataFrame) -> dict:
    """VIX / VIX3M on the latest date both exist, plus 1y history and percentile."""
    vix, v3m = close["^VIX"].dropna(), close["^VIX3M"].dropna()
    ratio = (vix / v3m).dropna()
    if ratio.empty:
        raise ValueError("no overlapping VIX / VIX3M data")
    last = ratio.index[-1]
    r = float(ratio.iloc[-1])
    yr = ratio.loc[last - pd.DateOffset(years=1):]
    v9 = clean(close["^VIX9D"].get(last)) if "^VIX9D" in close else None
    return {
        "asof": last.strftime("%Y-%m-%d"),
        "vix": round(float(vix[last]), 2), "vix3m": round(float(v3m[last]), 2),
        "vix9d": round(v9, 2) if v9 is not None else None,
        "ratio": round(r, 3),
        "ratio_prev": round(float(ratio.iloc[-2]), 3) if len(ratio) > 1 else None,
        "state": "backwardation" if r > 1.0 else "flat" if r >= 0.95 else "contango",
        "percentile_1y": round(float((yr <= r).mean() * 100), 0) if len(yr) >= 20 else None,
        "history": [[d.strftime("%Y-%m-%d"), round(float(v), 3)] for d, v in yr.items()],
    }


def build_sentiment() -> Sentiment:
    reg = load_yaml("sentiment.yaml")
    fg = fg_err = vt = vt_err = None
    try:
        fg = cnn.fetch()
        for c in fg["components"]:
            c["description"] = reg["components"].get(c["id"])
        fg["about"] = reg["fear_greed"]["about"]
    except Exception as e:  # noqa: BLE001
        fg_err = f"CNN Fear & Greed unavailable: {str(e)[:200]}"
        log.warning("sentiment: %s", fg_err)
    try:
        px = yahoo.fetch_prices(["^VIX", "^VIX3M", "^VIX9D"], period="2y")
        vt = {**vix_term_structure(px.close), "about": reg["vix_term"]["about"],
              "source_url": reg["vix_term"]["source_url"]}
    except Exception as e:  # noqa: BLE001
        vt_err = f"VIX term structure unavailable: {str(e)[:200]}"
        log.warning("sentiment: %s", vt_err)
    if fg is None and vt is None:
        raise RuntimeError(f"{fg_err}; {vt_err}")
    return Sentiment(generated_at=now_iso(), fear_greed=fg, fear_greed_error=fg_err,
                     vix_term=vt, vix_term_error=vt_err)


# ── News ───────────────────────────────────────────────────────────────────

def build_news() -> News:
    reg = load_yaml("news.yaml")
    compiled = news.compile_rules(reg["tag_rules"], reg.get("tag_exclude"))
    now = datetime.now(timezone.utc)
    cutoff = now - pd.Timedelta(hours=reg["window_hours"])
    all_items, sources = [], []
    for f in reg["feeds"]:
        try:
            items = news.parse_feed(news.fetch_feed(f), f, compiled)
            recent = [i for i in items if datetime.fromisoformat(i["published"]) >= cutoff]
            all_items += items
            sources.append({"id": f["id"], "source": f["source"], "url": f["url"], "ok": True,
                            "count": len(recent)})
        except Exception as e:  # noqa: BLE001
            log.warning("news feed %s failed: %s", f["id"], e)
            sources.append({"id": f["id"], "source": f["source"], "url": f["url"], "ok": False,
                            "count": 0, "error": str(e)[:200]})
    if not any(s["ok"] for s in sources):
        raise RuntimeError("all news feeds failed")
    items = news.select_items(all_items, now, reg["window_hours"], reg["max_items"], reg["max_per_feed"])
    return News(generated_at=now_iso(), window_hours=reg["window_hours"], sources=sources, items=items)


# ── Earnings ───────────────────────────────────────────────────────────────

def build_earnings() -> Earnings:
    reg = load_yaml("earnings.yaml")
    comps = reg["companies"]
    items, failed = earnings.fetch_upcoming(comps, days=reg["window_days"], pause=reg["throttle_seconds"])
    if len(failed) == len(comps):
        raise RuntimeError("earnings lookup failed for every ticker")
    if failed:
        log.warning("earnings: %d tickers failed: %s", len(failed), ", ".join(failed))
    return Earnings(generated_at=now_iso(), window_days=reg["window_days"], universe_size=len(comps),
                    failed=failed, about=reg["about"], items=items)


def build_sp500() -> SP500:
    reg = load_yaml("sp500.yaml")
    comps = reg["companies"]
    tickers = [c["t"] for c in comps]
    close = sp500.fetch_closes(tickers, period="4y", chunk_size=reg["chunk_size"])

    # Share counts are one Yahoo request per ticker and change slowly: refresh them all on
    # Saturday (the full rebuild) and otherwise only fetch the ones we don't have cached yet.
    prev_path = OUT / "sp500.json"
    cached: dict[str, float] = {}
    prev_prices: dict[str, float] = {}
    prev_asof = None
    if prev_path.exists():
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
            cached = {r["t"]: float(r["shares"]) for r in prev["rows"]}
            prev_prices = {r["t"]: float(r["price"]) for r in prev["rows"]}
            prev_asof = prev["asof"]
        except (ValueError, KeyError, TypeError):
            log.warning("sp500.json unreadable, refetching all share counts")
    refresh_all = datetime.now(timezone.utc).weekday() == 5 or not cached
    split_suspects = [] if refresh_all else sp500_tx.stale_share_tickers(prev_prices, prev_asof, close)
    if split_suspects:
        log.warning("sp500: possible stock split, refetching shares for: %s", ", ".join(split_suspects))
    need = tickers if refresh_all else [t for t in tickers if t not in cached or t in split_suspects]
    fresh = sp500.fetch_shares(need) if need else {}
    shares = {**cached, **fresh}  # a failed refresh keeps the cached count

    rows, failed = sp500_tx.build_rows(comps, close, shares)
    if failed:
        log.warning("sp500: %d tickers without price or share count: %s", len(failed), ", ".join(failed))
    if len(failed) > reg["max_missing_share"] * len(tickers):
        # Fail the section so the last good sp500.json is kept and flagged stale.
        raise RuntimeError(f"S&P 500 data missing for {len(failed)} of {len(tickers)} tickers")
    asof = close.dropna(how="all").index[-1].strftime("%Y-%m-%d")
    dates, series = sp500_tx.weekly_history(close, [r["t"] for r in rows])
    write_json("sp500_hist.json", SP500History(generated_at=now_iso(), asof=asof, dates=dates, series=series))
    return SP500(generated_at=now_iso(), asof=asof, periods=PERIODS, source_url=reg["source_url"],
                 about=reg["about"], failed=failed, rows=rows)


# "regime" then "insights" must stay LAST: they read the JSON the other sections just wrote.
# regime is code only (no keys); insights adds LLM text on top of it.
SECTIONS = ["markets", "economy", "yield_curve", "calendar", "uk", "positioning", "sentiment", "news", "earnings",
            "sp500", "regime", "insights"]
DERIVED = ["regime", "insights"]
EXTRA_BUILDERS = {  # independent sections: no inputs from other sections
    "uk": build_uk, "positioning": build_positioning, "sentiment": build_sentiment,
    "news": build_news, "earnings": build_earnings, "sp500": build_sp500,
}


# ── Orchestration ──────────────────────────────────────────────────────────

def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", choices=SECTIONS)
    args = ap.parse_args(argv)
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for h in logging.getLogger().handlers:  # urllib3 retry warnings include full URLs
        h.addFilter(RedactingFilter())

    sections = args.only or SECTIONS
    # derived sections always run after the data sections, in this order, whatever the --only order
    sections = [s for s in sections if s not in DERIVED] + [s for s in DERIVED if s in sections]
    meta_path = OUT / "meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"sections": {}}
    meta.setdefault("sections", {})

    economy = None
    status_ok = True
    for name in sections:
        try:
            if name == "markets":
                model = build_markets()
            elif name == "economy":
                model = economy = build_economy()
            elif name == "yield_curve":
                model = build_yield_curve()
            elif name == "regime":
                model = build_regime(OUT)
            elif name == "insights":
                model = build_insights(OUT)
            elif name in EXTRA_BUILDERS:
                model = EXTRA_BUILDERS[name]()
            else:
                if economy is None and (OUT / "economy.json").exists():
                    economy = Economy.model_validate_json((OUT / "economy.json").read_text())
                model = build_calendar(economy)
            write_json(f"{name}.json", model)
            meta["sections"][name] = {"ok": True, "updated_at": now_iso()}
            if name == "insights" and getattr(model, "provider", "") == "code":
                # Published, but not by an LLM: keep the failure visible (Stale badge, red job).
                status_ok = False
                meta["sections"][name].update({"ok": False, "failed_at": now_iso(),
                                               "error": "All AI providers failed or were rejected by the fact check; showing a code-written auto-summary"})
        except NoProviderAvailable as e:
            # Not a failure: no LLM key configured. Keep any previous insights.json untouched;
            # "skipped" + "note" let the UI explain why instead of flagging it stale.
            note = f"Skipped: {redact(str(e))}. Previous output kept."
            log.info("section %s skipped: %s", name, note)
            prev = meta["sections"].get(name, {})
            meta["sections"][name] = {**({"updated_at": prev["updated_at"]} if "updated_at" in prev else {}),
                                      "ok": True, "skipped": True, "note": note, "checked_at": now_iso()}
        except Exception as e:  # noqa: BLE001
            status_ok = False
            err = redact(f"{type(e).__name__}: {e}")
            log.error("section %s failed: %s", name, err)
            log.debug(redact(traceback.format_exc()))
            # Drop a previous run's "skipped"/"note" (e.g. "no LLM key"): it no longer applies.
            prev = {k: v for k, v in meta["sections"].get(name, {}).items()
                    if k not in ("skipped", "note", "checked_at")}
            # meta.json is PUBLIC (committed + deployed): only ever store redacted text.
            meta["sections"][name] = {**prev, "ok": False, "error": err[:300], "failed_at": now_iso()}

    meta["generated_at"] = now_iso()
    write_json("meta.json", meta)
    return 0 if status_ok else 1


if __name__ == "__main__":
    sys.exit(main())
