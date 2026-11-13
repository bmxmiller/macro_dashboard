"""Tests for pipeline.fetchers.fomc.parse on an inline fixture (no network)."""
from __future__ import annotations

from pipeline.fetchers import fomc


def meeting(month: str, dates: str) -> str:
    return (
        '<div class="row fomc-meeting">\n'
        f'  <div class="fomc-meeting__month col-xs-5 col-sm-3 col-md-2"><strong>{month}</strong></div>\n'
        f'  <div class="fomc-meeting__date col-xs-4 col-sm-9 col-md-10 col-lg-1">{dates}</div>\n'
        '  <div class="col-xs-12 col-md-4 col-lg-2"><a href="/statement.htm">Statement</a></div>\n'
        '</div>\n'
    )


def section(year: int, *rows: str) -> str:
    return (
        '<div class="panel panel-default">\n'
        f'  <div class="panel-heading"><h4><a id="{year}">{year} FOMC Meetings</a></h4></div>\n'
        + "".join(rows)
        + "</div>\n"
    )


HTML = (
    '<html><body><div id="article"><h3>Meeting calendars, statements, and minutes</h3>\n'
    + section(
        2026,
        meeting("January", "27-28"),
        meeting("March", "17-18*"),
        meeting("April/May", "30-1"),
        meeting("June", "16-17*"),
        meeting("December", "8-9*"),
    )
    + section(
        2025,
        meeting("December", "9-10*"),
        meeting("October", "28-29"),
    )
    + "</div></body></html>"
)


def test_parse_dates_use_last_meeting_day_sorted_across_years():
    dates = [m["date"] for m in fomc.parse(HTML)]
    assert dates == [
        "2025-10-29", "2025-12-10",
        "2026-01-28", "2026-03-18", "2026-05-01", "2026-06-17", "2026-12-09",
    ]


def test_parse_sep_flag():
    out = {m["date"]: m for m in fomc.parse(HTML)}
    assert out["2026-03-18"]["sep"] is True
    assert out["2026-06-17"]["sep"] is True
    assert out["2026-01-28"]["sep"] is False
    assert out["2026-05-01"]["sep"] is False
    assert all(m["notation_vote"] is False for m in out.values())


def test_parse_cross_month_meeting_uses_second_month():
    out = {m["date"] for m in fomc.parse(HTML)}
    assert "2026-05-01" in out
    assert not any(d.startswith("2026-04") for d in out)


def test_parse_dedupes_and_skips_bad_rows():
    html = section(
        2026,
        meeting("January", "27-28"),
        meeting("January", "27-28"),
        meeting("Smarch", "1-2"),           # unknown month
        meeting("February", "30-31"),       # impossible date
        meeting("March", "(unscheduled)"),  # no day numbers
    )
    assert fomc.parse(html) == [{"date": "2026-01-28", "sep": False, "notation_vote": False}]


def test_parse_drops_notation_votes():
    html = section(2026, meeting("January", "27-28"), meeting("August", "5 (notation vote)"))
    assert [m["date"] for m in fomc.parse(html)] == ["2026-01-28"]


def test_parse_no_sections_returns_empty():
    assert fomc.parse("<html><body>nothing here</body></html>") == []
