"""FOMC meeting dates scraped from the Federal Reserve's public calendar page."""
from __future__ import annotations

import re
from datetime import date

from .http import get

URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], start=1)}

# Fallback if the page layout changes (official 2026 schedule).
FALLBACK_2026 = [(1, 28), (3, 18), (4, 29), (6, 17), (7, 29), (9, 16), (10, 28), (12, 9)]
SEP_MONTHS_FALLBACK = {3, 6, 9, 12}


def parse(html: str) -> list[dict]:
    meetings = []
    parts = re.split(r"(\d{4}) FOMC Meetings", html)
    # parts = [pre, year, body, year, body, ...]
    for year_s, body in zip(parts[1::2], parts[2::2]):
        year = int(year_s)
        months = re.findall(r'fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*([A-Za-z/ ]+)', body)
        dates = re.findall(r'fomc-meeting__date[^>]*>\s*([^<]+)<', body)
        for m_raw, d_raw in zip(months, dates):
            m_last = m_raw.strip().split("/")[-1].strip().lower()
            if m_last not in MONTHS:
                continue
            d_clean = d_raw.strip()
            nums = re.findall(r"\d+", d_clean)
            if not nums:
                continue
            day = int(nums[-1])  # decision / statement day = last day of meeting
            try:
                dt = date(year, MONTHS[m_last], day)
            except ValueError:
                continue
            meetings.append({
                "date": dt.isoformat(),
                "sep": "*" in d_clean,
                "notation_vote": "notation" in d_clean.lower(),
            })
    seen, out = set(), []
    for m in sorted(meetings, key=lambda x: x["date"]):
        if m["date"] not in seen and not m["notation_vote"]:
            seen.add(m["date"])
            out.append(m)
    return out


def fetch_meetings() -> list[dict]:
    try:
        res = parse(get(URL).text)
        if res:
            return res
    except Exception:  # noqa: BLE001
        pass
    return [{"date": date(2026, m, d).isoformat(), "sep": m in SEP_MONTHS_FALLBACK, "notation_vote": False}
            for m, d in FALLBACK_2026]
