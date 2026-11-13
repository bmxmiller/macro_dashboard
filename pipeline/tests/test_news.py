from datetime import datetime, timedelta, timezone

from pipeline.fetchers import news

RULES = news.compile_rules({
    "rates": ["yield", "yields", "rate cut", "gilt"],
    "equities": ["stocks", "s&p 500", "s&p"],
    "central-bank": ["fed", "bank of england"],
    "uk": ["uk", "gilt", "bank of england"],
})

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>t</title>
<item><title>Fed signals rate cut &amp; yields fall</title><link>https://ex.com/a</link>
  <pubDate>Fri, 13 Nov 2026 10:00:00 GMT</pubDate>
  <description>&lt;p&gt;Treasury &lt;b&gt;yields&lt;/b&gt; dropped.&lt;/p&gt;</description></item>
<item><title>My husband says we can’t retire</title><link>https://ex.com/b</link>
  <pubDate>Fri, 13 Nov 2026 09:00:00 GMT</pubDate></item>
<item><title>No date item</title><link>https://ex.com/c</link></item>
</channel></rss>"""


def test_strip_html_and_truncate():
    assert news.strip_html("<p>Hello&nbsp;<b>world</b></p>") == "Hello world"
    long = "word " * 100
    out = news.strip_html(long, limit=50)
    assert len(out) <= 51 and out.endswith("…")
    assert news.strip_html(None) == ""


def test_normalize_title_unifies_quotes_and_punctuation():
    a = news.normalize_title("Fed’s Powell: “No rush” to cut")
    b = news.normalize_title("Fed's Powell -- \"No rush\" to cut!")
    assert a == b == "feds powell no rush to cut"


def test_tag_text_word_boundaries_and_base_tags():
    assert news.tag_text("S&P 500 hits record as stocks rally", RULES) == ["equities"]
    assert news.tag_text("Federal agency news; feedback", RULES) == []  # 'fed' must be a whole word
    assert news.tag_text("Gilt yields jump", RULES, base=["uk"]) == ["rates", "uk"]
    assert news.tag_text("Bank of England holds", RULES, base=["central-bank", "uk"]) == ["central-bank", "uk"]


def test_parse_feed_skips_undated_and_requires_tags():
    feed = {"id": "x", "source": "X", "tags": [], "require_tags": True}
    items = news.parse_feed(RSS.encode(), feed, RULES)
    assert [i["url"] for i in items] == ["https://ex.com/a"]
    it = items[0]
    assert it["title"] == "Fed signals rate cut & yields fall"
    assert it["summary"] == "Treasury yields dropped."
    assert it["published"] == "2026-11-13T10:00:00+00:00"
    assert it["tags"] == ["rates", "central-bank"]
    feed2 = {"id": "y", "source": "Y", "tags": []}
    assert len(news.parse_feed(RSS.encode(), feed2, RULES)) == 2


def _item(title, feed, hours_ago, now):
    return {"title": title, "feed": feed, "published": (now - timedelta(hours=hours_ago)).isoformat()}


def test_select_items_window_dedupe_caps_and_order():
    now = datetime(2026, 11, 13, 12, tzinfo=timezone.utc)
    items = [
        _item("Fed holds rates", "fed", 5, now),
        _item("FED HOLDS RATES!", "cnbc", 1, now),   # duplicate: first feed wins
        _item("Old story", "cnbc", 100, now),        # outside window
        _item("A", "cnbc", 2, now), _item("B", "cnbc", 3, now), _item("C", "cnbc", 4, now),
    ]
    out = news.select_items(items, now, window_hours=72, max_items=10, max_per_feed=2)
    assert [i["title"] for i in out] == ["A", "B", "Fed holds rates"]
    assert len(news.select_items(items, now, 72, 1, 10)) == 1
